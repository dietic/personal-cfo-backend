#!/usr/bin/env python3
"""
Reset all users and seed a fresh test set:
- 2 FREE, 2 PLUS, 2 PRO, 1 ADMIN
All are set active with plan_status=active and default categories+keywords created.

Usage (from repo root with docker):
  docker compose exec backend python /app/app/scripts/reset_and_seed_users.py
"""
import sys
import os
from typing import List

# Ensure app package is importable when run inside container
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(CURRENT_DIR)
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app.core.database import get_db
from app.models.user import User, UserTypeEnum
from app.core.security import get_password_hash
from app.services.user_service import UserService
from app.services.category_service import CategoryService
from app.services.keyword_service import KeywordService


def purge_all_users() -> int:
    """Hard-delete all users and their related data using existing purge logic."""
    db = next(get_db())
    try:
        users: List[User] = db.query(User).all()
        count = 0
        svc = UserService(db)
        for u in users:
            # Use email-based purge to cascade-delete dependents safely
            ok = svc.purge_user_by_email(u.email)
            count += 1 if ok else 0
        return count
    finally:
        db.close()


def create_users() -> List[str]:
    """Create the requested set of users and seed categories+keywords."""
    users_to_create = [
        {"email": "free1@personal-cfo.io", "plan_tier": UserTypeEnum.FREE, "is_admin": False, "first_name": "Free", "last_name": "One"},
        {"email": "free2@personal-cfo.io", "plan_tier": UserTypeEnum.FREE, "is_admin": False, "first_name": "Free", "last_name": "Two"},
        {"email": "plus1@personal-cfo.io", "plan_tier": UserTypeEnum.PLUS, "is_admin": False, "first_name": "Plus", "last_name": "One"},
        {"email": "plus2@personal-cfo.io", "plan_tier": UserTypeEnum.PLUS, "is_admin": False, "first_name": "Plus", "last_name": "Two"},
        {"email": "pro1@personal-cfo.io",  "plan_tier": UserTypeEnum.PRO,  "is_admin": False, "first_name": "Pro",  "last_name": "One"},
        {"email": "pro2@personal-cfo.io",  "plan_tier": UserTypeEnum.PRO,  "is_admin": False, "first_name": "Pro",  "last_name": "Two"},
        {"email": "admin@personal-cfo.io","plan_tier": UserTypeEnum.FREE,"is_admin": True,  "first_name": "Admin","last_name": "User"},
    ]

    default_password = "testpass123"
    password_hash = get_password_hash(default_password)

    db = next(get_db())
    created: List[str] = []
    try:
        for data in users_to_create:
            # Upsert-like behavior: if exists, update tier/flags and reactivate
            user = db.query(User).filter(User.email == data["email"]).first()
            if user is None:
                user = User(
                    email=data["email"],
                    password_hash=password_hash,
                    plan_tier=data["plan_tier"],
                    is_admin=data["is_admin"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    is_active=True,
                    plan_status="active",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                created.append(user.email)
            else:
                user.plan_tier = data["plan_tier"]
                user.is_admin = data["is_admin"]
                user.first_name = data["first_name"]
                user.last_name = data["last_name"]
                user.is_active = True
                user.plan_status = "active"
                db.commit()
                db.refresh(user)
                created.append(user.email + " (updated)")

            # Ensure default categories and keywords per user
            CategoryService.create_default_categories(db, user.id)
            KeywordService(db).seed_default_keywords(str(user.id))

        db.commit()
        return created
    finally:
        db.close()


def main():
    purged = purge_all_users()
    print(f"Purged {purged} existing users")
    created = create_users()
    print("Created/updated users:")
    for email in created:
        print(f" - {email}")
    print("All test users password: 'testpass123'")


if __name__ == "__main__":
    main()
