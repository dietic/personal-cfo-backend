from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import json
import uuid

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryKeywordMatch
from app.core.exceptions import NotFoundError, ValidationError


class CategoryService:
    
    @staticmethod
    def create_default_categories(db: Session, user_id: uuid.UUID) -> List[Category]:
        """Create default categories for a new user"""
        default_categories = [
            {"name": "Food & Dining", "color": "#FF6B6B", "keywords": ["restaurant", "food", "dining", "lunch", "breakfast", "dinner", "cafe", "coffee", "pizza", "burger", "grocery", "supermarket"]},
            {"name": "Transportation", "color": "#4ECDC4", "keywords": ["gas", "fuel", "uber", "lyft", "taxi", "bus", "train", "metro", "parking", "toll", "car", "auto"]},
            {"name": "Shopping", "color": "#45B7D1", "keywords": ["amazon", "store", "mall", "shop", "retail", "clothing", "clothes", "purchase", "buy"]},
            {"name": "Entertainment", "color": "#96CEB4", "keywords": ["movie", "cinema", "theater", "concert", "game", "spotify", "netflix", "entertainment", "fun", "leisure"]},
            {"name": "Utilities", "color": "#FFEAA7", "keywords": ["electric", "electricity", "water", "gas", "internet", "phone", "mobile", "utility", "bill", "power"]},
            {"name": "Healthcare", "color": "#DDA0DD", "keywords": ["doctor", "hospital", "pharmacy", "medical", "health", "dentist", "clinic", "medicine", "prescription"]},
            {"name": "Housing", "color": "#F39C12", "keywords": ["rent", "mortgage", "home", "house", "apartment", "property", "maintenance", "repair", "insurance"]},
        ]
        
        categories = []
        for cat_data in default_categories:
            category = Category(
                user_id=user_id,
                name=cat_data["name"],
                color=cat_data["color"],
                keywords=json.dumps(cat_data["keywords"]),
                is_default=True,
                is_active=True
            )
            db.add(category)
            categories.append(category)
        
        db.commit()
        return categories
    
    @staticmethod
    def get_user_categories(db: Session, user_id: uuid.UUID, include_inactive: bool = False) -> List[Category]:
        """Get all categories for a user (including system categories)"""
        query = db.query(Category).filter(
            (Category.user_id == user_id) | (Category.is_system == True)  # User categories OR system categories
        )
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        return query.order_by(Category.name).all()
    
    @staticmethod
    def get_category_count(db: Session, user_id: uuid.UUID) -> int:
        """Get the number of active categories for a user (including system categories)"""
        return db.query(Category).filter(
            (Category.user_id == user_id) | (Category.is_system == True),  # User categories OR system categories
            Category.is_active == True
        ).count()
    
    @staticmethod
    def create_category(db: Session, user_id: uuid.UUID, category_data: CategoryCreate) -> Category:
        """Create a new category for a user"""
        # Check if category name already exists for this user
        existing = db.query(Category).filter(
            Category.user_id == user_id,
            Category.name.ilike(category_data.name.strip()),
            Category.is_active == True
        ).first()
        
        if existing:
            raise ValidationError(f"Category '{category_data.name}' already exists")
        
        # Convert keywords list to JSON string
        keywords_json = json.dumps(category_data.keywords) if category_data.keywords else None
        
        category = Category(
            user_id=user_id,
            name=category_data.name.strip(),
            color=category_data.color,
            keywords=keywords_json,
            is_default=False,
            is_active=category_data.is_active
        )
        
        db.add(category)
        db.commit()
        db.refresh(category)
        return category
    
    @staticmethod
    def update_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID, category_data: CategoryUpdate) -> Category:
        """Update an existing category"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id
        ).first()
        
        if not category:
            raise NotFoundError("Category not found")
        
        # Check if new name conflicts with existing categories
        if category_data.name and category_data.name.strip() != category.name:
            existing = db.query(Category).filter(
                Category.user_id == user_id,
                Category.name.ilike(category_data.name.strip()),
                Category.is_active == True,
                Category.id != category_id
            ).first()
            
            if existing:
                raise ValidationError(f"Category '{category_data.name}' already exists")
            
            category.name = category_data.name.strip()
        
        if category_data.color is not None:
            category.color = category_data.color
        
        if category_data.keywords is not None:
            category.keywords = json.dumps(category_data.keywords) if category_data.keywords else None
        
        if category_data.is_active is not None:
            category.is_active = category_data.is_active
        
        db.commit()
        db.refresh(category)
        return category
    
    @staticmethod
    def delete_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> bool:
        """Soft delete a category (mark as inactive)"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id
        ).first()
        
        if not category:
            raise NotFoundError("Category not found")
        
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
            if not category.keywords:
                continue
            
            try:
                # Handle both string (JSON) and list formats
                if isinstance(category.keywords, str):
                    keywords = json.loads(category.keywords)
                elif isinstance(category.keywords, list):
                    keywords = category.keywords
                else:
                    continue
            except (json.JSONDecodeError, TypeError):
                continue
            
            matched_keywords = []
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.lower() in text_to_match:
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
        
        # Add "Uncategorized" as fallback option
        if "Uncategorized" not in category_names:
            category_names.append("Uncategorized")
            
        return category_names
