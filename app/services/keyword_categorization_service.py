"""
Keyword-based categorization service that replaces AI categorization.
Provides deterministic transaction categorization using user-defined keywords.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from app.models.category_keyword import CategoryKeyword
from app.models.category import Category
from app.models.transaction import Transaction
from app.services.keyword_service import KeywordService
from app.schemas.category import CategoryKeywordMatch

logger = logging.getLogger(__name__)


class KeywordCategorizationService:
    """Service for pure keyword-based transaction categorization"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.keyword_service = KeywordService(db_session)
    
    def categorize_transaction(self, user_id: str, merchant: str, description: str = "") -> Optional[CategoryKeywordMatch]:
        """
        Categorize a single transaction using keyword matching.
        Returns the best matching category with confidence score.
        """
        # Get all user keywords
        keywords = self.keyword_service.get_user_keywords(user_id)
        
        if not keywords:
            logger.warning(f"No keywords found for user {user_id}")
            return None
        
        text_to_match = f"{merchant} {description}".lower().strip()
        # Normalize apostrophes and spaces for consistent matching
        text_to_match = text_to_match.replace("'", "")
        text_to_match = text_to_match.replace(" ", "")
        
        # Group keywords by category and find matches
        category_matches = {}
        
        for keyword_obj in keywords:
            keyword_text = keyword_obj.keyword.lower()
            
            if keyword_text in text_to_match:
                category_id = keyword_obj.category_id
                category_name = keyword_obj.category.name if keyword_obj.category else "Unknown"
                
                if category_id not in category_matches:
                    category_matches[category_id] = {
                        'category_name': category_name,
                        'matched_keywords': [],
                        'total_keywords': 0
                    }
                
                category_matches[category_id]['matched_keywords'].append(keyword_text)
        
        # Count total keywords per category to calculate confidence
        for keyword_obj in keywords:
            category_id = keyword_obj.category_id
            if category_id in category_matches:
                category_matches[category_id]['total_keywords'] += 1
        
        if not category_matches:
            logger.info(f"No keyword matches found for: {text_to_match}")
            return None
        
        # Find the best match (highest confidence)
        best_category_id = None
        best_confidence = 0.0
        best_match_data = None
        
        for category_id, match_data in category_matches.items():
            matched_count = len(match_data['matched_keywords'])
            total_count = max(match_data['total_keywords'], 1)
            
            # Base confidence on ratio of matched keywords
            confidence = matched_count / total_count
            
            # Boost confidence for multiple matches
            if matched_count > 1:
                confidence += 0.1 * (matched_count - 1)
            
            # Boost confidence for longer keywords
            for keyword in match_data['matched_keywords']:
                if len(keyword) > 5:
                    confidence += 0.05
            
            # Ensure confidence doesn't exceed 1.0
            confidence = min(confidence, 1.0)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_category_id = category_id
                best_match_data = match_data
        
        if best_match_data:
            return CategoryKeywordMatch(
                category_id=best_category_id,
                category_name=best_match_data['category_name'],
                matched_keywords=best_match_data['matched_keywords'],
                confidence=best_confidence
            )
        
        return None
    
    def categorize_transactions_batch(
        self, 
        user_id: str, 
        transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Categorize multiple transactions using keyword matching.
        
        Args:
            user_id: User ID
            transactions: List of transaction dicts with 'merchant', 'description', etc.
            
        Returns:
            List of transaction dicts with added 'category' and 'confidence' fields
        """
        categorized_transactions = []
        
        for txn in transactions:
            merchant = txn.get('merchant', txn.get('description', ''))
            description = txn.get('description', '')
            
            # Attempt keyword categorization
            match = self.categorize_transaction(user_id, merchant, description)
            
            # Add categorization results to transaction
            categorized_txn = txn.copy()
            
            if match:
                categorized_txn['category'] = match.category_name
                categorized_txn['confidence'] = match.confidence
                categorized_txn['categorization_method'] = 'keyword'
                categorized_txn['matched_keywords'] = match.matched_keywords
                logger.info(f"Keyword categorized: {merchant} -> {match.category_name} (confidence: {match.confidence:.2f})")
            else:
                # Default to "Sin categoría" if no keywords match
                categorized_txn['category'] = 'Sin categoría'
                categorized_txn['confidence'] = 0.0
                categorized_txn['categorization_method'] = 'default'
                categorized_txn['matched_keywords'] = []
                logger.info(f"No keyword match for: {merchant}, defaulting to Sin categoría")
            
            categorized_transactions.append(categorized_txn)
        
        return categorized_transactions
    
    def categorize_database_transactions(
        self, 
        user_id: str, 
        transactions: List[Transaction],
        force_recategorize: bool = False
    ) -> Dict[str, Any]:
        """
        Categorize Transaction objects in the database using keywords.
        
        Args:
            user_id: User ID
            transactions: List of Transaction model objects
            force_recategorize: Whether to recategorize already categorized transactions
            
        Returns:
            Dictionary with categorization results and statistics
        """
        results = {
            'total_transactions': len(transactions),
            'categorized': 0,
            'uncategorized': 0,
            'categorization_details': []
        }

        for transaction in transactions:
            # Skip if already categorized (unless force_recategorize is True)
            if not force_recategorize and transaction.category and transaction.category != 'Sin categoría':
                results['categorized'] += 1
                results['categorization_details'].append({
                    'transaction_id': str(transaction.id),
                    'method': 'existing',
                    'category': transaction.category,
                    'confidence': getattr(transaction, 'ai_confidence', 1.0)
                })
                continue

            # Attempt keyword categorization
            match = self.categorize_transaction(
                user_id, 
                transaction.merchant, 
                transaction.description or ""
            )
            
            if match:
                # Update transaction with keyword categorization
                transaction.category = match.category_name
                transaction.ai_confidence = match.confidence
                
                results['categorized'] += 1
                results['categorization_details'].append({
                    'transaction_id': str(transaction.id),
                    'method': 'keyword',
                    'category': match.category_name,
                    'confidence': match.confidence,
                    'matched_keywords': match.matched_keywords
                })
                
                logger.info(f"Keyword categorized transaction {transaction.id}: {transaction.merchant} -> {match.category_name}")
            else:
                # Set to uncategorized
                transaction.category = 'Sin categoría'
                transaction.ai_confidence = 0.0
                
                results['uncategorized'] += 1
                results['categorization_details'].append({
                    'transaction_id': str(transaction.id),
                    'method': 'uncategorized',
                    'category': 'Sin categoría',
                    'confidence': 0.0
                })
                
                logger.info(f"No keyword match for transaction {transaction.id}: {transaction.merchant}")
        
        # Commit changes to database
        try:
            self.db.commit()
            logger.info(f"Keyword categorization completed: {results['categorized']} categorized, {results['uncategorized']} uncategorized")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to commit keyword categorization: {str(e)}")
            raise
        
        return results
    
    def get_categorization_preview(
        self, 
        user_id: str, 
        transaction_descriptions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Preview how transactions would be categorized without saving to database.
        Useful for testing keyword configurations.
        
        Args:
            user_id: User ID
            transaction_descriptions: List of transaction descriptions to test
            
        Returns:
            List of categorization previews
        """
        previews = []
        
        for description in transaction_descriptions:
            match = self.categorize_transaction(user_id, description, "")
            
            preview = {
                'description': description,
                'would_categorize': match is not None
            }
            
            if match:
                preview.update({
                    'category': match.category_name,
                    'confidence': match.confidence,
                    'matched_keywords': match.matched_keywords
                })
            else:
                preview.update({
                    'category': 'Sin categoría',
                    'confidence': 0.0,
                    'matched_keywords': []
                })
            
            previews.append(preview)
        
        return previews
    
    def get_coverage_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about keyword coverage for the user.
        
        Returns:
            Dictionary with coverage statistics
        """
        keywords = self.keyword_service.get_user_keywords(user_id)
        categories = self.db.query(Category).filter(Category.user_id == user_id).all()
        
        stats = {
            'total_categories': len(categories),
            'categories_with_keywords': 0,
            'categories_without_keywords': 0,
            'total_keywords': len(keywords),
            'keywords_per_category': {},
            'coverage_percentage': 0.0
        }
        
        # Group keywords by category
        keywords_by_category = {}
        for keyword in keywords:
            category_id = keyword.category_id
            if category_id not in keywords_by_category:
                keywords_by_category[category_id] = []
            keywords_by_category[category_id].append(keyword)
        
        # Calculate coverage statistics
        for category in categories:
            category_keywords = keywords_by_category.get(category.id, [])
            keyword_count = len(category_keywords)
            
            stats['keywords_per_category'][category.name] = {
                'count': keyword_count,
                'keywords': [kw.keyword for kw in category_keywords]
            }
            
            if keyword_count > 0:
                stats['categories_with_keywords'] += 1
            else:
                stats['categories_without_keywords'] += 1
        
        # Calculate coverage percentage
        if stats['total_categories'] > 0:
            stats['coverage_percentage'] = (stats['categories_with_keywords'] / stats['total_categories']) * 100
        
        return stats
