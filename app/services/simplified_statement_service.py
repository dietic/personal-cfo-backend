"""
Simplified Statement Service with OpenAI-driven extraction and categorization
New approach: Extract + Categorize in one step using predefined Spanish categories
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import json
import uuid
from datetime import datetime, date
import logging
import PyPDF2
import io

from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.category import Category
from app.models.card import Card
from app.services.ai_service import AIService
from app.core.exceptions import ValidationError, ProcessingError

logger = logging.getLogger(__name__)


class SimplifiedStatementService:
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
    
    def get_spanish_categories(self) -> List[str]:
        """Get all Spanish categories from database"""
        categories = self.db.query(Category).filter(Category.is_active == True).all()
        return [cat.name for cat in categories]
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF using PyPDF2"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise ProcessingError(f"Could not extract text from PDF: {str(e)}")
    
    def extract_and_categorize_with_openai(
        self, 
        text_content: str,
        spanish_categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Use OpenAI to extract and categorize transactions in one call
        """
        categories_text = ", ".join(spanish_categories)
        
        prompt = f"""
Analiza este estado de cuenta bancario y extrae TODAS las transacciones.

Para cada transacción, proporciona:
1. transaction_date (formato YYYY-MM-DD)
2. description (descripción clara del comercio/concepto)
3. amount (número decimal, positivo para cargos, negativo para abonos/depósitos)
4. currency (código de 3 letras como USD, PEN, EUR)
5. category (DEBE ser una de estas categorías exactas): {categories_text}

REGLAS IMPORTANTES:
- Si no puedes categorizar una transacción con certeza, usa "Misc"
- Los montos deben ser números decimales (ejemplo: 15.50, no "$15.50")
- Las fechas deben estar en formato YYYY-MM-DD
- Extrae TODAS las transacciones, no omitas ninguna
- Si hay comisiones o cargos bancarios, inclúyelos también

Responde ÚNICAMENTE con un JSON array válido, sin texto adicional:

[
  {{
    "transaction_date": "2024-01-15",
    "description": "Supermercado Metro",
    "amount": 45.80,
    "currency": "PEN",
    "category": "Supermercado"
  }},
  ...
]

Estado de cuenta:
{text_content}
"""

        try:
            response = self.ai_service.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert financial document parser. Always respond with valid JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ProcessingError("Empty response from OpenAI")
            
            # Parse JSON response
            try:
                transactions = json.loads(content)
                if not isinstance(transactions, list):
                    raise ProcessingError("OpenAI response is not a list")
                return transactions
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {str(e)}")
                logger.error(f"Response content: {content}")
                raise ProcessingError(f"Invalid JSON response from OpenAI: {str(e)}")
                
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise ProcessingError(f"Failed to process with OpenAI: {str(e)}")
    
    def validate_extracted_transactions(
        self, 
        transactions: List[Dict], 
        valid_categories: List[str]
    ) -> List[Dict[str, Any]]:
        """Validate and clean extracted transactions"""
        validated = []
        
        for i, txn in enumerate(transactions):
            try:
                # Validate required fields
                required_fields = ['transaction_date', 'description', 'amount', 'currency', 'category']
                for field in required_fields:
                    if field not in txn:
                        logger.warning(f"Transaction {i} missing field: {field}")
                        continue
                
                # Validate and convert date
                try:
                    if isinstance(txn['transaction_date'], str):
                        txn_date = datetime.strptime(txn['transaction_date'], '%Y-%m-%d').date()
                    else:
                        txn_date = txn['transaction_date']
                except ValueError:
                    logger.warning(f"Invalid date format in transaction {i}: {txn['transaction_date']}")
                    continue
                
                # Validate amount
                try:
                    amount = float(txn['amount'])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount in transaction {i}: {txn['amount']}")
                    continue
                
                # Validate category
                category = txn['category']
                if category not in valid_categories:
                    logger.warning(f"Invalid category '{category}' in transaction {i}, using 'Misc'")
                    category = 'Misc'
                
                # Validate currency
                currency = txn.get('currency', 'USD')
                if len(currency) != 3:
                    logger.warning(f"Invalid currency '{currency}' in transaction {i}, using 'USD'")
                    currency = 'USD'
                
                validated.append({
                    'transaction_date': txn_date,
                    'description': str(txn['description']).strip(),
                    'amount': amount,
                    'currency': currency.upper(),
                    'category': category
                })
                
            except Exception as e:
                logger.warning(f"Error validating transaction {i}: {str(e)}")
                continue
        
        return validated
    
    def process_statement_new_approach(
        self, 
        statement_id: uuid.UUID,
        file_content: bytes
    ) -> Dict[str, Any]:
        """
        Process statement with new approach: extract + categorize in one step
        """
        try:
            # Get statement
            statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
            if not statement:
                raise ValidationError(f"Statement {statement_id} not found")
            
            # Update status
            statement.status = "processing"
            statement.extraction_status = "in_progress"
            statement.categorization_status = "in_progress"
            self.db.commit()
            
            # Get Spanish categories
            spanish_categories = self.get_spanish_categories()
            if not spanish_categories:
                raise ProcessingError("No Spanish categories available in database")
            
            logger.info(f"Found {len(spanish_categories)} Spanish categories for processing")
            
            # Extract text from PDF
            if statement.file_type.lower() == 'pdf':
                text_content = self.extract_text_from_pdf(file_content)
            else:
                text_content = file_content.decode('utf-8')
            
            # Extract and categorize with OpenAI
            transactions_data = self.extract_and_categorize_with_openai(
                text_content, spanish_categories
            )
            
            # Validate transactions
            validated_transactions = self.validate_extracted_transactions(
                transactions_data, spanish_categories
            )
            
            if not validated_transactions:
                raise ProcessingError("No valid transactions extracted")
            
            # Get user's cards for transaction creation
            user_cards = self.db.query(Card).filter(Card.user_id == statement.user_id).all()
            if not user_cards:
                raise ValidationError("User has no cards configured")
            
            # Use first card as default
            default_card = user_cards[0]
            
            # Create Transaction objects
            created_transactions = []
            for txn_data in validated_transactions:
                transaction = Transaction(
                    card_id=default_card.id,
                    statement_id=statement.id,  # Link to statement
                    merchant=txn_data['description'],
                    amount=txn_data['amount'],
                    currency=txn_data['currency'],
                    category=txn_data['category'],
                    transaction_date=txn_data['transaction_date'],
                    description=txn_data['description'],
                    ai_confidence=0.95  # High confidence for AI categorization
                )
                
                self.db.add(transaction)
                created_transactions.append(transaction)
            
            # Store processed transactions as JSON for backwards compatibility
            statement.processed_transactions = json.dumps([
                {
                    "description": txn_data['description'],
                    "amount": float(txn_data['amount']),
                    "currency": txn_data['currency'],
                    "category": txn_data['category'],
                    "transaction_date": txn_data['transaction_date'].isoformat(),
                }
                for txn_data in validated_transactions
            ])
            
            # Update statement status
            statement.status = "completed"
            statement.extraction_status = "completed"
            statement.categorization_status = "completed"
            statement.is_processed = True
            
            # Commit all changes
            self.db.commit()
            
            result = {
                "statement_id": str(statement.id),
                "status": statement.status,
                "transactions_count": len(created_transactions),
                "approach": "new_single_step",
                "categories_used": len(spanish_categories),
                "transactions": [
                    {
                        "id": str(txn.id),
                        "description": txn.description,
                        "amount": float(txn.amount),
                        "currency": txn.currency,
                        "category": txn.category,
                        "transaction_date": txn.transaction_date.isoformat(),
                    }
                    for txn in created_transactions
                ]
            }
            
            logger.info(f"Successfully processed statement {statement_id} with NEW approach: {len(created_transactions)} transactions")
            return result
            
        except Exception as e:
            # Rollback and update error status
            self.db.rollback()
            
            statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
            if statement:
                statement.status = "failed"
                statement.error_message = str(e)
                self.db.commit()
            
            logger.error(f"Error processing statement {statement_id} with NEW approach: {str(e)}")
            raise ProcessingError(f"Failed to process statement: {str(e)}")
    
    def get_statement_status(self, statement_id: uuid.UUID) -> Dict[str, Any]:
        """Get current status of statement processing"""
        statement = self.db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            raise ValidationError(f"Statement {statement_id} not found")
        
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
