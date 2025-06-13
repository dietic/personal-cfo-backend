#!/usr/bin/env python3

"""
Simple statement extraction service that works around the enhanced service issues
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import uuid
import logging
from datetime import datetime

from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.card import Card
from app.services.statement_parser import StatementParser

logger = logging.getLogger(__name__)


class SimpleStatementService:
    """A simplified statement service that avoids the complex type issues"""
    
    @staticmethod
    def extract_transactions_simple(
        db: Session, 
        statement_id: uuid.UUID, 
        card_id: Optional[uuid.UUID] = None,
        card_name: Optional[str] = None,
        statement_month: Optional[str] = None
    ) -> Dict[str, Any]:
        """Simple extraction that works around the enhanced service issues"""
        
        # Get statement using raw SQL to avoid SQLAlchemy column issues
        result = db.execute(
            "SELECT id, user_id, filename, file_path, file_type, status FROM statements WHERE id = ?",
            (str(statement_id),)
        ).fetchone()
        
        if not result:
            raise ValueError("Statement not found")
        
        statement_id_str, user_id_str, filename, file_path, file_type, status = result
        
        try:
            # Update status to extracting
            db.execute(
                "UPDATE statements SET status = ?, extraction_status = ? WHERE id = ?",
                ("extracting", "in_progress", str(statement_id))
            )
            db.commit()
            
            # Parse the statement file
            parser = StatementParser()
            
            if file_type.lower() == 'pdf':
                transactions_data = parser.parse_pdf(file_path)
            elif file_type.lower() == 'csv':
                transactions_data = parser.parse_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            if not transactions_data:
                raise ValueError("No transactions found in statement")
            
            # Get or create card
            card = None
            if card_id:
                card = db.query(Card).filter(
                    Card.id == card_id,
                    Card.user_id == uuid.UUID(user_id_str)
                ).first()
            elif card_name:
                card = db.query(Card).filter(
                    Card.user_id == uuid.UUID(user_id_str),
                    Card.card_name.ilike(f"%{card_name}%")
                ).first()
            
            if not card:
                # Create a new card if none found
                card = Card(
                    user_id=uuid.UUID(user_id_str),
                    card_name=card_name or f"Card from {filename}",
                    card_type="credit",  # Default type
                    last_four_digits="0000",
                    is_active=True
                )
                db.add(card)
                db.commit()
                db.refresh(card)
            
            # Create transaction objects
            transactions = []
            for trans_data in transactions_data:
                transaction = Transaction(
                    card_id=card.id,
                    merchant=trans_data.get('merchant', 'Unknown'),
                    amount=trans_data.get('amount', 0.0),
                    currency=trans_data.get('currency', 'USD'),
                    transaction_date=trans_data.get('transaction_date'),
                    description=trans_data.get('description', ''),
                    category=None,  # Will be set during categorization
                    ai_confidence=None
                )
                transactions.append(transaction)
            
            # Save transactions to database
            db.add_all(transactions)
            db.commit()
            
            # Update statement status
            db.execute(
                "UPDATE statements SET status = ?, extraction_status = ?, categorization_status = ? WHERE id = ?",
                ("extracted", "completed", "pending", str(statement_id))
            )
            db.commit()
            
            logger.info(f"Successfully extracted {len(transactions)} transactions from statement {statement_id}")
            
            return {
                "statement_id": statement_id,
                "transactions_found": len(transactions),
                "card_id": card.id,
                "card_name": card.card_name,
                "status": "extracted",
                "message": f"Successfully extracted {len(transactions)} transactions"
            }
            
        except Exception as e:
            logger.error(f"Extraction failed for statement {statement_id}: {str(e)}")
            
            # Update status to failed
            db.execute(
                "UPDATE statements SET status = ?, extraction_status = ?, error_message = ? WHERE id = ?",
                ("failed", "failed", f"Extraction failed: {str(e)}", str(statement_id))
            )
            db.commit()
            
            raise ValueError(f"Failed to extract transactions: {str(e)}")
