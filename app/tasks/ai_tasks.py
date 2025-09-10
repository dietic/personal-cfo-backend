"""
Celery tasks for AI-related background processing.
"""
from celery import shared_task
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.ai_keyword_service import AIKeywordService
from app.models.user import User
from app.models.category import Category

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_ai_keywords_task(self, user_id: str, category_id: str, clear_existing: bool = False):
    """
    Background task to generate AI keywords for a category.
    """
    db: Session = SessionLocal()
    try:
        # Get user and category
        user = db.query(User).filter(User.id == user_id).first()
        category = db.query(Category).filter(Category.id == category_id).first()
        
        if not user or not category:
            raise ValueError("User or category not found")
        
        # Create AI keyword service
        ai_keyword_service = AIKeywordService(db)
        
        # Generate keywords (this will use the request object for IP detection)
        # For background tasks, we'll use a default country since we don't have request context
        country_code = "PE"  # Default to Peru for background tasks
        
        # Generate keywords
        keywords = ai_keyword_service.generate_category_keywords(user, category, country_code, 20)
        
        # Log the generated keywords for debugging
        print(f"Generated {len(keywords)} AI keywords for category {category.name}")
        print(f"Keywords: {keywords}")
        
        # Add keywords to category
        added_keywords = []
        for keyword_text in keywords:
            try:
                keyword = category.add_keyword(
                    keyword_text=keyword_text,
                    description=f"AI-generated keyword for {category.name}"
                )
                db.add(keyword)
                added_keywords.append(keyword)
            except ValueError:
                # Keyword already exists, skip
                continue
        
        # Update category and user usage
        from sqlalchemy import func
        category.ai_seeded_at = func.now()
        ai_keyword_service.increment_ai_usage(user)
        
        db.commit()
        
        return {
            "success": True,
            "keywords_added": len(added_keywords),
            "category_id": category_id,
            "category_name": category.name
        }
        
    except Exception as e:
        db.rollback()
        # Retry the task if it fails
        self.retry(exc=e)
    finally:
        db.close()