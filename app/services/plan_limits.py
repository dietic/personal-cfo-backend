from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.card import Card
from app.models.statement import Statement
from app.models.budget import Budget
from app.models.alert import Alert
from app.models.category import Category

PLAN_LIMITS = {
    "free": {
        "cards": 1,
        "statements": 2,
        "budgets": 2,
        "alerts": 2,
        "categories": 5,  # total categories (default only – block custom creation)
    },
    "plus": {
        "cards": 5,
        "statements": None,  # None => unlimited
        "budgets": 10,
        "alerts": 6,
        "categories": 25,  # custom allowed up to 25
    },
    "pro": {
        "cards": None,
        "statements": None,
        "budgets": 15,
        "alerts": 10,
        "categories": None,
    },
}

UPGRADE_SUGGESTIONS = {
    "cards": "Upgrade your plan to add more cards.",
    "statements": "Upgrade to import more statements.",
    "budgets": "Upgrade to create additional budgets.",
    "alerts": "Upgrade to configure more alerts.",
    "categories": "Upgrade to create more custom categories.",
}


def _limit(plan: str, key: str):
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).get(key)


LIMITED_RESOURCES = ["cards", "statements", "budgets", "alerts", "categories"]


def _plan_key(user: User) -> str:
    """Return the string key for the user's plan (e.g. 'free', 'plus').
    Supports SQLAlchemy Enum instances by unwrapping `.value`.
    """
    plan = user.plan_tier
    # If it's an Enum (has .value), unwrap to the string; else use as-is or fallback
    return getattr(plan, "value", plan) or "free"


def assert_within_limit(db: Session, user: User, resource: str):
    if user.is_admin:
        return
    plan = _plan_key(user)
    limit = _limit(plan, resource)
    if limit is None:
        return  # unlimited

    # Count current usage
    if resource == "cards":
        count = db.query(Card).filter(Card.user_id == user.id).count()
    elif resource == "statements":
        count = db.query(Statement).filter(Statement.user_id == user.id).count()
    elif resource == "budgets":
        count = db.query(Budget).filter(Budget.user_id == user.id).count()
    elif resource == "alerts":
        count = db.query(Alert).filter(Alert.user_id == user.id).count()
    elif resource == "categories":
        # Only count custom (non-default) user categories toward plan limits
        count = db.query(Category).filter(
            Category.user_id == user.id,
            Category.is_default == False
        ).count()
    else:
        return

    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": f"{resource.capitalize()} limit reached for your plan ({plan}).",
                "resource": resource,
                "limit": limit,
                "current": count,
                "plan": plan,
                "action": UPGRADE_SUGGESTIONS.get(resource, "Upgrade your plan."),
            },
        )


def get_plan_usage(db: Session, user: User):
    """Return dict of current usage vs. limits for quick UI consumption."""
    if user.is_admin:
        return {r: {"current": 0, "limit": None} for r in LIMITED_RESOURCES}
    plan = _plan_key(user)
    usage = {}
    for r in LIMITED_RESOURCES:
        limit = _limit(plan, r)
        if r == "cards":
            current = db.query(Card).filter(Card.user_id == user.id).count()
        elif r == "statements":
            current = db.query(Statement).filter(Statement.user_id == user.id).count()
        elif r == "budgets":
            current = db.query(Budget).filter(Budget.user_id == user.id).count()
        elif r == "alerts":
            current = db.query(Alert).filter(Alert.user_id == user.id).count()
        elif r == "categories":
            # Report only custom category count against the limit
            current = db.query(Category).filter(
                Category.user_id == user.id,
                Category.is_default == False
            ).count()
        else:
            current = 0
        usage[r] = {"current": current, "limit": limit}
    return usage
