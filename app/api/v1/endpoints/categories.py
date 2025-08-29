from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid

from app.core.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.category import Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryWithUsage,
    CategoryKeywordMatch
)
from app.services.category_service import CategoryService
from app.services.categorization_service import CategorizationService
from app.services.plan_limits import assert_within_limit
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter()


@router.get("/")
def get_categories(
    include_inactive: bool = Query(False, description="Include inactive categories"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all categories for the current user.
    If the user has no categories yet (e.g., migrated/free accounts), create the 5 defaults.
    """
    categories = CategoryService.get_user_categories(
        db=db,
        user_id=current_user.id,
        include_inactive=include_inactive
    )

    # If a user has no categories at all, seed the 5 fixed defaults on the fly
    if not categories:
        try:
            CategoryService.create_default_categories(db=db, user_id=current_user.id)
            categories = CategoryService.get_user_categories(
                db=db,
                user_id=current_user.id,
                include_inactive=include_inactive,
            )
        except Exception:
            # Do not block response; fall through with empty list
            categories = []

    # Convert to response format with keywords populated
    response_categories = []
    for category in categories:
        can_modify = CategoryService.can_modify_category(db, current_user, category.id)
        response_categories.append(CategoryResponse(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            color=category.color,
            is_default=category.is_default,
            is_active=category.is_active,
            can_modify=can_modify,
            keywords=category.get_keyword_strings(),
            created_at=category.created_at,
            updated_at=category.updated_at
        ))

    # Add user permissions to response
    can_modify_categories = CategoryService.can_modify_categories(current_user)

    return {
        "categories": response_categories,
        "permissions": {
            "can_create_categories": can_modify_categories,
            "can_edit_categories": can_modify_categories,
            "can_delete_categories": can_modify_categories,
            "plan_tier": current_user.plan_tier.value if current_user.plan_tier else "free",
            "message": "Upgrade your plan to create and manage custom categories" if not can_modify_categories else "You can create and manage custom categories"
        }
    }


@router.get("/stats", response_model=Dict[str, Any])
def get_category_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get category usage statistics"""
    stats = CategoryService.get_category_usage_stats(db=db, user_id=current_user.id)
    return stats


@router.get("/validate-minimum")
def validate_minimum_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check if user has minimum required categories for statement upload"""
    is_valid = CategoryService.validate_minimum_categories(db=db, user_id=current_user.id)
    count = CategoryService.get_category_count(db=db, user_id=current_user.id)

    return {
        "has_minimum": is_valid,
        "current_count": count,
        "minimum_required": 5,
        "message": "Ready to upload statements" if is_valid else f"Need {5 - count} more categories"
    }


@router.get("/permissions")
def get_category_permissions(
    current_user: User = Depends(get_current_active_user)
):
    """Get category modification permissions for current user"""
    can_modify = CategoryService.can_modify_categories(current_user)

    return {
        "can_create_categories": can_modify,
        "can_edit_categories": can_modify,
        "can_delete_categories": can_modify,
        "plan_tier": current_user.plan_tier.value if current_user.plan_tier else "free",
        "message": "Upgrade your plan to create and manage custom categories" if not can_modify else "You can create and manage custom categories"
    }


@router.post("/", response_model=CategoryResponse)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new category"""
    # Enforce plan category limits (only for user-owned)
    assert_within_limit(db, current_user, "categories")

    try:
        category = CategoryService.create_category(
            db=db,
            user_id=current_user.id,
            user=current_user,
            category_data=category_data
        )
        # Add can_modify field for response
        can_modify = CategoryService.can_modify_category(db, current_user, category.id)
        return CategoryResponse(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            color=category.color,
            is_default=category.is_default,
            is_active=category.is_active,
            can_modify=can_modify,
            keywords=category.get_keyword_strings(),
            created_at=category.created_at,
            updated_at=category.updated_at
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing category"""
    try:
        category = CategoryService.update_category(
            db=db,
            user_id=current_user.id,
            user=current_user,
            category_id=category_id,
            category_data=category_data
        )
        # Add can_modify field for response
        can_modify = CategoryService.can_modify_category(db, current_user, category.id)
        return CategoryResponse(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            color=category.color,
            is_default=category.is_default,
            is_active=category.is_active,
            can_modify=can_modify,
            keywords=category.get_keyword_strings(),
            created_at=category.created_at,
            updated_at=category.updated_at
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a category (soft delete if used by transactions)"""
    try:
        was_hard_deleted = CategoryService.delete_category(
            db=db,
            user_id=current_user.id,
            user=current_user,
            category_id=category_id
        )

        return {
            "message": "Category deleted successfully" if was_hard_deleted else "Category deactivated (used by transactions)",
            "hard_deleted": was_hard_deleted
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-defaults", response_model=List[CategoryResponse])
def create_default_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create default categories for the user"""
    existing_count = CategoryService.get_category_count(db=db, user_id=current_user.id)

    if existing_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"User already has {existing_count} categories. Default categories are only created for new users."
        )

    categories = CategoryService.create_default_categories(db=db, user_id=current_user.id)

    # Convert to response format with keywords populated
    response_categories = []
    for category in categories:
        can_modify = CategoryService.can_modify_category(db, current_user, category.id)
        response_categories.append(CategoryResponse(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            color=category.color,
            is_default=category.is_default,
            is_active=category.is_active,
            can_modify=can_modify,
            keywords=category.get_keyword_strings(),
            created_at=category.created_at,
            updated_at=category.updated_at
        ))

    return response_categories


@router.get("/suggest/{merchant}")
def get_categorization_suggestions(
    merchant: str,
    description: Optional[str] = Query(None),
    amount: Optional[float] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get categorization suggestions for a merchant"""
    suggestions = CategorizationService.get_categorization_suggestions(
        db=db,
        user_id=current_user.id,
        merchant=merchant,
        description=description or "",
        amount=amount or 0.0
    )

    return {
        "merchant": merchant,
        "suggestions": suggestions
    }


@router.post("/test-keywords")
def test_keyword_matching(
    merchant: str,
    description: Optional[str] = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Test keyword matching for a merchant/description"""
    match = CategoryService.categorize_by_keywords(
        db=db,
        user_id=current_user.id,
        merchant=merchant,
        description=description or ""
    )

    if match:
        return {
            "merchant": merchant,
            "description": description,
            "match_found": True,
            "category": match.category_name,
            "confidence": match.confidence,
            "matched_keywords": match.matched_keywords
        }
    else:
        return {
            "merchant": merchant,
            "description": description,
            "match_found": False,
            "message": "No keyword matches found"
        }
