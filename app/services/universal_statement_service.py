"""
Enhanced AI-powered statement service that can process any bank statement.
This service uses the AIStatementExtractor to handle statements from any bank
without requiring specific pattern mappings.
"""
import json
import logging
import uuid
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError, ProcessingError
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.card import Card
from app.models.category import Category
from app.services.clean_ai_extractor import CleanAIStatementExtractor
from app.services.keyword_categorization_service import KeywordCategorizationService
from app.services.excluded_keywords_service import ExcludedKeywordsService

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CATEGORY = "Sin categoría"
MAX_RETRIES = 3


class UniversalStatementService:
    """
Universal Statement Service for handling PDF statement processing.

This service uses the CleanAIStatementExtractor to handle statements from any bank
and provides categorization and validation of transactions.
"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.ai_extractor = CleanAIStatementExtractor(db_session)
        self.keyword_categorization = KeywordCategorizationService(db_session)

    def process_statement(
        self,
        statement_id: uuid.UUID,
        file_content: bytes,
        password: Optional[str] = None,
        use_keyword_categorization: bool = True
    ) -> Dict[str, Any]:
        """
        Process a statement using AI extraction and optional keyword categorization.
        AI extraction is the primary and only method for transaction extraction.
        """
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")

        try:
            # Update status to processing
            statement.status = "processing"
            statement.extraction_status = "in_progress"
            statement.categorization_status = "in_progress"
            self.db.commit()

            logger.info(f"Starting universal processing for statement {statement_id}")

            # Extract transactions using AI (primary and only method)
            transactions_data = self._extract_with_ai(statement, file_content, password)

            if not transactions_data:
                raise ProcessingError("No transactions found in statement")

            logger.info(f"Extracted {len(transactions_data)} transactions")

            # NEW: Apply per-user excluded keywords filter (skip before saving)
            try:
                ek_service = ExcludedKeywordsService(self.db)
                ek_service.seed_defaults_if_empty(str(statement.user_id))
                before = len(transactions_data)
                filtered = []
                skipped = 0
                for t in transactions_data:
                    merchant = t.get("merchant", "") or ""
                    description = t.get("description", merchant) or ""
                    if ek_service.should_exclude(str(statement.user_id), merchant, description):
                        skipped += 1
                        continue
                    filtered.append(t)
                transactions_data = filtered
                logger.info(f"Excluded-keywords filter skipped {skipped} of {before} transactions for user {statement.user_id}")
            except Exception as fe:
                logger.warning(f"Excluded-keywords filter failed: {fe}. Proceeding without filtering.")

            if not transactions_data:
                raise ProcessingError("All transactions were excluded by user keywords")

            # Step 2: Apply keyword categorization if enabled (enhances AI categories)
            if use_keyword_categorization:
                transactions_data = self._enhance_with_keywords(transactions_data, str(statement.user_id))

            # Step 3: Get or create default card
            default_card = self._get_or_create_default_card(statement)

            # Step 4: Create Transaction objects in database
            created_transactions = self._create_transactions(
                transactions_data, default_card, statement_id
            )

            # Step 5: Update statement status
            statement.status = "completed"
            statement.extraction_status = "completed"
            statement.categorization_status = "completed"
            statement.is_processed = True

            # Store transaction summary with UTF-8 safe encoding
            safe_transaction_data = []
            for txn in created_transactions:
                # Ensure all string fields are UTF-8 safe
                safe_txn = {
                    "id": str(txn.id),
                    "merchant": txn.merchant.encode('utf-8', errors='ignore').decode('utf-8') if txn.merchant else "",
                    "amount": float(txn.amount),
                    "currency": txn.currency,
                    "category": txn.category.encode('utf-8', errors='ignore').decode('utf-8') if txn.category else "",
                    "transaction_date": txn.transaction_date.isoformat()
                }
                safe_transaction_data.append(safe_txn)

            statement.processed_transactions = json.dumps(safe_transaction_data, ensure_ascii=False)

            self.db.commit()

            result = {
                "statement_id": str(statement.id),
                "status": statement.status,
                "transactions_count": len(created_transactions),
                "extraction_method": "ai",
                "keyword_enhancement": use_keyword_categorization,
                "transactions": [
                    {
                        "id": str(txn.id),
                        "merchant": txn.merchant.encode('utf-8', errors='ignore').decode('utf-8') if txn.merchant else "",
                        "amount": float(txn.amount),
                        "currency": txn.currency,
                        "category": txn.category.encode('utf-8', errors='ignore').decode('utf-8') if txn.category else "",
                        "transaction_date": txn.transaction_date.isoformat(),
                        "description": txn.description.encode('utf-8', errors='ignore').decode('utf-8') if txn.description else ""
                    }
                    for txn in created_transactions
                ]
            }

            logger.info(f"Successfully processed statement {statement_id} with {len(created_transactions)} transactions")
            return result

        except Exception as e:
            # Rollback and update error status
            self.db.rollback()

            statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
            if statement:
                statement.status = "failed"
                statement.error_message = str(e)
                self._increment_retry_count(statement, "extraction")
                self.db.commit()

            logger.error(f"Failed to process statement {statement_id}: {str(e)}")
            raise ProcessingError(f"Failed to process statement: {str(e)}")

    def _extract_with_ai(
        self,
        statement: Statement,
        file_content: bytes,
        password: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract transactions using AI (primary method)"""
        try:
            if statement.file_type.lower() == 'pdf':
                # Use enhanced AI extraction (direct PDF processing)
                transactions = self.ai_extractor.extract_transactions(
                    file_content,
                    str(statement.user_id),
                    password
                )

            elif statement.file_type.lower() == 'csv':
                # Handle CSV files
                transactions = self.ai_extractor.extract_from_csv(
                    file_content,
                    str(statement.user_id),
                    statement.filename
                )

            else:
                raise ProcessingError(f"Unsupported file type: {statement.file_type}")

            return transactions

        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            raise ProcessingError(f"AI extraction failed: {str(e)}")

    def _enhance_with_keywords(
        self,
        transactions_data: List[Dict[str, Any]],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Enhance AI-extracted transactions with keyword-based categorization.
        This can improve category accuracy by combining AI + user's custom keywords.
        """
        try:
            enhanced_transactions = []

            for txn_data in transactions_data:
                # Try keyword categorization
                keyword_result = self.keyword_categorization.categorize_transaction(
                    user_id,
                    txn_data.get('merchant', ''),
                    txn_data.get('description', '')
                )

                # Use keyword category if found (any confidence > 0)
                if keyword_result and keyword_result.confidence > 0.0:
                    txn_data['category'] = keyword_result.category_name
                    txn_data['categorization_method'] = 'keyword'
                    logger.info(f"Keyword categorized: {txn_data.get('merchant', '')} -> {keyword_result.category_name} (confidence: {keyword_result.confidence:.2f})")
                else:
                    # Keep AI category if no keyword match, or default to "Sin categoría"
                    if 'category' not in txn_data or not txn_data['category']:
                        txn_data['category'] = 'Sin categoría'
                    txn_data['categorization_method'] = 'ai'

                enhanced_transactions.append(txn_data)

            return enhanced_transactions

        except Exception as e:
            logger.warning(f"Keyword enhancement failed: {str(e)}, using AI categories only")
            return transactions_data

    def _get_or_create_default_card(self, statement: Statement) -> Card:
        """Get user's card or create a default one"""
        # Try to find an existing card for this user
        existing_cards = self.db.query(Card).filter(Card.user_id == statement.user_id).all()

        if existing_cards:
            # Use the first available card
            return existing_cards[0]

        # Create a default card if none exists
        default_card = Card(
            user_id=statement.user_id,
            card_name=f"Default Card - {statement.filename}",
            card_type="credit",
            bank_provider="Unknown Bank",
            network_provider="VISA"
        )

        self.db.add(default_card)
        self.db.commit()
        self.db.refresh(default_card)

        return default_card

    def _create_transactions(
        self,
        transactions_data: List[Dict[str, Any]],
        card: Card,
        statement_id: uuid.UUID
    ) -> List[Transaction]:
        """Create Transaction objects in the database"""
        created_transactions = []

        for txn_data in transactions_data:
            try:
                transaction = Transaction(
                    card_id=card.id,
                    statement_id=statement_id,
                    merchant=txn_data['merchant'],
                    amount=txn_data['amount'],
                    currency=txn_data['currency'],
                    transaction_date=txn_data['transaction_date'],
                    description=txn_data.get('description', txn_data['merchant']),
                    category=txn_data.get('category', DEFAULT_CATEGORY),
                    ai_confidence=0.95  # High confidence for AI extraction
                )

                self.db.add(transaction)
                created_transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Failed to create transaction: {str(e)}")
                continue

        return created_transactions

    def _increment_retry_count(self, statement: Statement, retry_type: str):
        """Increment retry count for extraction or categorization"""
        if retry_type == "extraction":
            if not hasattr(statement, 'extraction_retries'):
                statement.extraction_retries = 0
            statement.extraction_retries += 1
        elif retry_type == "categorization":
            if not hasattr(statement, 'categorization_retries'):
                statement.categorization_retries = 0
            statement.categorization_retries += 1

    def get_statement_status(self, statement_id: uuid.UUID) -> Dict[str, Any]:
        """Get current processing status of a statement"""
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")

        # Count linked transactions
        transaction_count = self.db.query(Transaction).filter(
            Transaction.statement_id == statement_id
        ).count()

        return {
            "statement_id": str(statement.id),
            "status": statement.status,
            "extraction_status": statement.extraction_status,
            "categorization_status": statement.categorization_status,
            "transactions_count": transaction_count,
            "error_message": statement.error_message,
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None
        }

    def retry_statement_processing(
        self,
        statement_id: uuid.UUID,
        use_keyword_categorization: bool = True
    ) -> Dict[str, Any]:
        """Retry processing a failed statement"""
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError("Statement not found")

        # Check retry limits
        max_retries = MAX_RETRIES
        extraction_retries = getattr(statement, 'extraction_retries', 0)

        if extraction_retries >= max_retries:
            raise ValidationError(f"Maximum retry attempts ({max_retries}) exceeded")

        # Clear previous error
        statement.error_message = None
        statement.status = "processing"
        self.db.commit()

        # Re-read the file content (assuming it's still available)
        if not statement.file_path or not os.path.exists(statement.file_path):
            raise ProcessingError("Original file not found for retry")

        with open(statement.file_path, 'rb') as file:
            file_content = file.read()

        # Retry processing
        return self.process_statement(
            statement_id,
            file_content,
            use_keyword_categorization=use_keyword_categorization
        )

    @staticmethod
    def is_ai_extraction_enabled() -> bool:
        """Check if AI extraction is enabled (API key available)"""
        from app.core.config import settings
        return bool(getattr(settings, 'OPENAI_API_KEY', None))

    def get_processing_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get processing statistics for a user"""
        user_statements = self.db.query(Statement).filter(Statement.user_id == user_id).all()

        total_statements = len(user_statements)
        completed_statements = len([s for s in user_statements if s.status == "completed"])
        failed_statements = len([s for s in user_statements if s.status == "failed"])

        total_transactions = self.db.query(Transaction).join(Card).filter(
            Card.user_id == user_id
        ).count()

        return {
            "total_statements": total_statements,
            "completed_statements": completed_statements,
            "failed_statements": failed_statements,
            "success_rate": completed_statements / total_statements if total_statements > 0 else 0,
            "total_transactions": total_transactions,
            "ai_extraction_available": self.is_ai_extraction_enabled()
        }
