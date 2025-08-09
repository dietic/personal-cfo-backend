import unicodedata
from typing import List
from sqlalchemy.orm import Session

from app.models.user_excluded_keyword import UserExcludedKeyword
from app.core.database import Base, engine

DEFAULT_EXCLUDED_KEYWORDS = [
    "INTERESES",
    "CONSUMO REVOLVENTE",
    "DESGRAVAMEN",
    "COMISIONES",
    "OTROS CARGOS",
    "SEGURO",
]


def _normalize(text: str) -> str:
    if not text:
        return ""
    # Lowercase, strip, remove diacritics
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


class ExcludedKeywordsService:
    """Manage per-user excluded transaction keywords and filtering logic."""

    def __init__(self, db: Session):
        self.db = db
        # Ensure table exists (idempotent)
        try:
            Base.metadata.create_all(bind=engine, tables=[UserExcludedKeyword.__table__])
        except Exception:
            # Ignore create errors if migrations handle this
            pass

    def list_keywords(self, user_id: str) -> List[UserExcludedKeyword]:
        return (
            self.db.query(UserExcludedKeyword)
            .filter(UserExcludedKeyword.user_id == user_id)
            .order_by(UserExcludedKeyword.keyword.asc())
            .all()
        )

    def seed_defaults_if_empty(self, user_id: str) -> None:
        existing = (
            self.db.query(UserExcludedKeyword)
            .filter(UserExcludedKeyword.user_id == user_id)
            .first()
        )
        if existing:
            return
        for kw in DEFAULT_EXCLUDED_KEYWORDS:
            self.add_keyword(user_id, kw)

    def add_keyword(self, user_id: str, keyword: str) -> UserExcludedKeyword:
        kw_norm = _normalize(keyword)
        # Check uniqueness for the user by normalized form
        exists = (
            self.db.query(UserExcludedKeyword)
            .filter(
                UserExcludedKeyword.user_id == user_id,
                UserExcludedKeyword.keyword_normalized == kw_norm,
            )
            .first()
        )
        if exists:
            return exists
        item = UserExcludedKeyword(
            user_id=user_id,
            keyword=keyword.strip(),
            keyword_normalized=kw_norm,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_keyword(self, user_id: str, keyword_id: str) -> bool:
        item = (
            self.db.query(UserExcludedKeyword)
            .filter(UserExcludedKeyword.user_id == user_id, UserExcludedKeyword.id == keyword_id)
            .first()
        )
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def reset_defaults(self, user_id: str) -> None:
        self.db.query(UserExcludedKeyword).filter(UserExcludedKeyword.user_id == user_id).delete()
        self.db.commit()
        for kw in DEFAULT_EXCLUDED_KEYWORDS:
            self.add_keyword(user_id, kw)

    def should_exclude(self, user_id: str, merchant: str, description: str) -> bool:
        # Fetch user keywords once; could cache if needed
        keywords = self.list_keywords(user_id)
        if not keywords:
            return False
        m = _normalize(merchant)
        d = _normalize(description)
        for k in keywords:
            kn = k.keyword_normalized
            if not kn:
                continue
            if kn in m or kn in d:
                return True
        return False
