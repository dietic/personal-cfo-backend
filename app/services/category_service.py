from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import uuid

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryKeywordMatch
from app.core.exceptions import NotFoundError, ValidationError

# Restricted category names that cannot be created by users
RESTRICTED_CATEGORY_NAMES = {"income", "ingreso"}


class CategoryService:

    @staticmethod
    def create_default_categories(db: Session, user_id: uuid.UUID) -> List[Category]:
        """Create default categories for a new user (5 fixed categories for free users)"""
        default_categories = [
            {"name": "Alimentación", "color": "#FF6B6B", "keywords": ["restaurante", "comida", "almuerzo", "desayuno", "cena", "café", "cafetería", "pizza", "hamburguesa", "supermercado", "mercado", "panadería", "carnicería", "delivery", "pedido"]},
            {"name": "Salud", "color": "#DDA0DD", "keywords": ["doctor", "médico", "hospital", "clínica", "farmacia", "medicina", "dentista", "consulta", "receta", "seguro médico", "copago", "urgencias", "cirugía", "terapia", "laboratorio"]},
            {"name": "Transporte", "color": "#4ECDC4", "keywords": ["gasolina", "combustible", "uber", "taxi", "bus", "metro", "tren", "estacionamiento", "peaje", "auto", "coche", "vehículo", "transporte", "bicicleta", "motocicleta"]},
            {"name": "Vivienda", "color": "#F39C12", "keywords": ["alquiler", "arriendo", "hipoteca", "casa", "apartamento", "propiedad", "mantenimiento", "reparación", "seguro hogar", "administración", "inquilino", "propietario", "inmobiliaria", "mudanza", "muebles"]},
            {"name": "Otros", "color": "#95A5A6", "keywords": ["varios", "otros", "miscelaneos", "general", "no categorizado", "sin categoría", "indefinido", "vario"]},
        ]

        categories = []
        for cat_data in default_categories:
            category = Category(
                user_id=user_id,
                name=cat_data["name"],
                color=cat_data["color"],
                is_default=True,
                is_active=True
            )
            db.add(category)
            categories.append(category)

        db.commit()

        # After creating categories, create keywords for each category
        # Import here to avoid circular import
        from app.models.category_keyword import CategoryKeyword

        for i, cat_data in enumerate(default_categories):
            category = categories[i]
            for keyword in cat_data["keywords"]:
                keyword_obj = CategoryKeyword(
                    user_id=user_id,
                    category_id=category.id,
                    keyword=keyword.lower().strip()
                )
                db.add(keyword_obj)

        db.commit()
        return categories

    @staticmethod
    def get_user_categories(db: Session, user_id: uuid.UUID, include_inactive: bool = False) -> List[Category]:
        """Get all categories for a user (only user-specific categories)"""
        query = db.query(Category).filter(
            Category.user_id == user_id  # Only user categories
        )
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        return query.order_by(Category.name).all()

    @staticmethod
    def get_category_count(db: Session, user_id: uuid.UUID) -> int:
        """Get the number of active categories for a user (only user-specific categories)"""
        return db.query(Category).filter(
            Category.user_id == user_id,  # Only user categories
            Category.is_active == True
        ).count()

    @staticmethod
    def can_modify_categories(user) -> bool:
        """Check if user can modify (create, edit, delete) categories"""
        # Import here to avoid circular import
        from app.models.user import UserTypeEnum
        # Free users cannot modify categories
        return user.plan_tier != UserTypeEnum.FREE and user.plan_tier is not None

    @staticmethod
    def can_modify_category(db: Session, user, category_id: uuid.UUID) -> bool:
        """Check if user can modify a specific category.
        Free users: cannot modify any categories.
        Plus/Pro/Admin: can modify any of their categories (including defaults).
        """
        from app.models.user import UserTypeEnum
        if user.plan_tier == UserTypeEnum.FREE:
            return False
        # Ensure the category exists and belongs to the user
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user.id
        ).first()
        return category is not None

    @staticmethod
    def create_category(db: Session, user_id: uuid.UUID, user, category_data: CategoryCreate) -> Category:
        """Create a new category for a user"""
        # Check if user can create categories
        if not CategoryService.can_modify_categories(user):
            raise ValidationError("Free users cannot create custom categories. Upgrade your plan to create custom categories.")

        # Validate category name is not restricted
        category_name = category_data.name.strip()
        if category_name.lower() in RESTRICTED_CATEGORY_NAMES:
            raise ValidationError(f"Category name '{category_name}' is restricted and cannot be used")

        # Check if category name already exists for this user
        existing = db.query(Category).filter(
            Category.user_id == user_id,
            Category.name.ilike(category_name),
            Category.is_active == True
        ).first()

        if existing:
            raise ValidationError(f"Category '{category_name}' already exists")

        category = Category(
            user_id=user_id,
            name=category_data.name.strip(),
            color=category_data.color,
            is_default=False,
            is_active=category_data.is_active
        )

        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def update_category(db: Session, user_id: uuid.UUID, user, category_id: uuid.UUID, category_data: CategoryUpdate) -> Category:
        """Update an existing category"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id
        ).first()

        if not category:
            raise NotFoundError("Category not found")

        # Check if user can modify this category
        if not CategoryService.can_modify_category(db, user, category_id):
            from app.models.user import UserTypeEnum
            if user.plan_tier == UserTypeEnum.FREE:
                raise ValidationError("Free users cannot modify categories. Upgrade your plan to create and edit custom categories.")
            else:
                raise ValidationError("Cannot modify this category.")

        # Check if new name conflicts with existing categories
        if category_data.name and category_data.name.strip() != category.name:
            new_category_name = category_data.name.strip()
            
            # Validate category name is not restricted
            if new_category_name.lower() in RESTRICTED_CATEGORY_NAMES:
                raise ValidationError(f"Category name '{new_category_name}' is restricted and cannot be used")

            existing = db.query(Category).filter(
                Category.user_id == user_id,
                Category.name.ilike(new_category_name),
                Category.is_active == True,
                Category.id != category_id
            ).first()

            if existing:
                raise ValidationError(f"Category '{new_category_name}' already exists")

            category.name = new_category_name

        if category_data.color is not None:
            category.color = category_data.color

        if category_data.is_active is not None:
            category.is_active = category_data.is_active

        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def delete_category(db: Session, user_id: uuid.UUID, user, category_id: uuid.UUID) -> bool:
        """Soft delete a category (mark as inactive)"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id
        ).first()

        if not category:
            raise NotFoundError("Category not found")

        # Check if user can modify this category
        if not CategoryService.can_modify_category(db, user, category_id):
            from app.models.user import UserTypeEnum
            if user.plan_tier == UserTypeEnum.FREE:
                raise ValidationError("Free users cannot delete categories. Upgrade your plan to create and manage custom categories.")
            else:
                raise ValidationError("Cannot delete this category.")

        # Check if category is being used by transactions
        transaction_count = db.query(Transaction).join(
            Transaction.card
        ).filter(
            Transaction.card.has(user_id=user_id),
            Transaction.category == category.name
        ).count()

        if transaction_count > 0:
            # Soft delete - mark as inactive
            category.is_active = False
            db.commit()
            return False  # Indicates soft delete
        else:
            # Hard delete if no transactions use it
            db.delete(category)
            db.commit()
            return True  # Indicates hard delete

    @staticmethod
    def categorize_by_keywords(db: Session, user_id: uuid.UUID, merchant: str, description: str = "") -> Optional[CategoryKeywordMatch]:
        """Find the best category match using keyword matching"""
        categories = CategoryService.get_user_categories(db, user_id)

        text_to_match = f"{merchant} {description}".lower().strip()
        best_match = None
        best_score = 0.0

        for category in categories:
            # Get keywords from the relationship
            keywords = category.get_keyword_strings()  # This returns list of keyword strings

            if not keywords:
                continue

            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text_to_match:
                    matched_keywords.append(keyword)

            if matched_keywords:
                # Calculate confidence based on number and length of matched keywords
                score = len(matched_keywords) / len(keywords)
                # Boost score for longer keyword matches
                for keyword in matched_keywords:
                    if len(keyword) > 5:
                        score += 0.1

                if score > best_score:
                    best_score = score
                    best_match = CategoryKeywordMatch(
                        category_id=category.id,
                        category_name=category.name,
                        matched_keywords=matched_keywords,
                        confidence=min(score, 1.0)
                    )

        return best_match

    @staticmethod
    def validate_minimum_categories(db: Session, user_id: uuid.UUID) -> bool:
        """Check if user has at least 5 active categories (including system categories)"""
        count = CategoryService.get_category_count(db, user_id)
        return count >= 5

    @staticmethod
    def get_category_usage_stats(db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get usage statistics for user categories"""
        categories = CategoryService.get_user_categories(db, user_id)
        stats = {
            "total_categories": len(categories),
            "default_categories": len([c for c in categories if c.is_default]),
            "custom_categories": len([c for c in categories if not c.is_default]),
            "categories_with_keywords": len([c for c in categories if c.keywords]),
            "usage_by_category": {}
        }

        # Get transaction counts per category
        for category in categories:
            count = db.query(Transaction).join(
                Transaction.card
            ).filter(
                Transaction.card.has(user_id=user_id),
                Transaction.category == category.name
            ).count()

            stats["usage_by_category"][category.name] = {
                "transaction_count": count,
                "is_default": category.is_default,
                "has_keywords": bool(category.keywords)
            }

        return stats

    @staticmethod
    def get_category_names_for_ai(db: Session, user_id: uuid.UUID) -> List[str]:
        """Get list of category names for AI processing (including system categories)"""
        categories = CategoryService.get_user_categories(db, user_id, include_inactive=False)
        category_names = [category.name for category in categories]

        # Add "Sin categoría" as fallback option
        if "Sin categoría" not in category_names:
            category_names.append("Sin categoría")

        return category_names
