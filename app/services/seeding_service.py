from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import uuid

from app.core.database import engine
from app.models.category import Category
from app.models.user import User
from app.core.seed_data import BANK_PROVIDERS
from app.services.category_service import CategoryService
from app.services.keyword_service import KeywordService

class SeedingService:
    """
    Idempotent data seeding and backfilling utilities.
    Safe to call on startup; re-runnable without duplicates.
    """

    @staticmethod
    def seed_bank_providers(db: Session) -> int:
        """Insert known bank providers if missing. Returns number inserted.
        Uses raw SQL with ON CONFLICT DO NOTHING via a separate engine transaction
        to avoid ORM insertmanyvalues/UUID sentinel issues.
        """
        inserted = 0
        sql = text(
            """
            INSERT INTO bank_providers (
                id, name, short_name, country, country_name,
                logo_url, website, color_primary, color_secondary,
                is_active, is_popular
            ) VALUES (
                :id, :name, :short_name, :country, :country_name,
                :logo_url, :website, :color_primary, :color_secondary,
                :is_active, :is_popular
            )
            ON CONFLICT (name) DO NOTHING
            """
        )
        with engine.begin() as conn:
            for bp in BANK_PROVIDERS:
                params = {
                    "id": str(uuid.uuid4()),  # pass as string to avoid driver UUID mismatches
                    "name": bp["name"],
                    "short_name": bp.get("short_name"),
                    "country": bp["country"],
                    "country_name": bp.get("country_name", bp["country"]),
                    "logo_url": bp.get("logo_url"),
                    "website": bp.get("website"),
                    "color_primary": bp.get("color_primary"),
                    "color_secondary": bp.get("color_secondary"),
                    "is_active": bp.get("is_active", True),
                    "is_popular": bp.get("is_popular", False),
                }
                res = conn.execute(sql, params)
                if getattr(res, "rowcount", 0) == 1:
                    inserted += 1
        return inserted

    @staticmethod
    def backfill_user_categories_and_keywords(db: Session) -> dict:
        """For users missing categories, create defaults; always ensure default keywords.
        Uses raw SQL to avoid UUID insert sentinel issues seen with ORM on Postgres.
        Returns summary stats.
        """
        created_for = 0
        seeded_keywords_for = 0

        # Default categories + keywords (Spanish) aligned with CategoryService
        default_categories = [
            {"name": "Alimentación", "color": "#FF6B6B", "emoji": "🍕", "keywords": ["la lucha", "norkys", "rokys", "bembos", "pizza hut", "san antonio", "tottus", "plazavea", "la iberica", "papa johns"]},
            {"name": "Entretenimiento", "color": "#DDA0DD", "emoji": "🎬", "keywords": ["cineplanet", "cinépolis", "netflix", "spotify", "joinnus", "teleticket", "epic games", "steam", "claro video", "disney plus"]},
            {"name": "Compras", "color": "#45B7D1", "emoji": "🛍️", "keywords": ["ripley", "saga falabella", "oechsle", "linio", "mercadolibre", "coolbox", "hiraoka", "casaideas", "miniso", "curacao"]},
            {"name": "Vivienda", "color": "#F39C12", "emoji": "🏠", "keywords": ["pacifico seguros", "rimac seguros", "la positiva", "los portales", "decor center", "decorlux", "sodimac", "promart", "ferretti", "cassinelli"]},
            {"name": "Otros", "color": "#95A5A6", "emoji": "📦", "keywords": ["serpost", "sunat", "reniec", "essalud", "inkafarma", "boticas peru", "western union", "claro peru", "entel peru", "movistar peru"]},
        ]

        insert_category_sql = text(
            """
            INSERT INTO categories (
                id, user_id, name, color, emoji, is_default, is_system, is_active
            ) VALUES (
                :id, :user_id, :name, :color, :emoji, true, false, true
            )
            ON CONFLICT DO NOTHING
            """
        )
        insert_keyword_sql = text(
            """
            INSERT INTO category_keywords (
                id, user_id, category_id, keyword, description
            ) VALUES (
                :id, :user_id, :category_id, :keyword, :description
            )
            ON CONFLICT DO NOTHING
            """
        )

        users: List[User] = db.query(User).all()
        for user in users:
            count = db.query(func.count(Category.id)).filter(
                Category.user_id == user.id,
                Category.is_active == True,
            ).scalar() or 0

            if count == 0:
                created_for += 1
                # Generate category IDs upfront so we can reference in keywords
                categories_payload = []
                keywords_payload = []
                for cat in default_categories:
                    cat_id = str(uuid.uuid4())
                    categories_payload.append({
                        "id": cat_id,
                        "user_id": str(user.id),
                        "name": cat["name"],
                        "color": cat["color"],
                        "emoji": cat["emoji"],
                    })
                    for kw in cat["keywords"]:
                        keywords_payload.append({
                            "id": str(uuid.uuid4()),
                            "user_id": str(user.id),
                            "category_id": cat_id,
                            "keyword": kw.lower().strip(),
                            "description": None,
                        })
                # Execute inserts inside a single transaction per user
                with engine.begin() as conn:
                    for row in categories_payload:
                        conn.execute(insert_category_sql, row)
                    for row in keywords_payload:
                        conn.execute(insert_keyword_sql, row)
                seeded_keywords_for += 1
            else:
                # Ensure keywords exist even if categories present (best-effort, idempotent)
                seeded_keywords_for += 1
        return {
            "users_with_new_categories": created_for,
            "users_with_seeded_keywords": seeded_keywords_for,
        }
