from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import json
import logging
# Fast processing endpoints for PersonalCFO
from datetime import datetime, date

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.card import Card
from app.models.alert import Alert, AlertType, AlertSeverity
from app.schemas.statement import (
    StatementCreate, 
    Statement as StatementSchema, 
    StatementProcess, 
    StatementProcessRequest,
    StatementStatusResponse,
    ExtractionRequest,
    ExtractionResponse,
    CategorizationRequest,
    CategorizationResponse,
    RetryRequest
)
from app.services.statement_parser import StatementParser
from app.services.ai_service import AIService
from app.services.enhanced_statement_service import EnhancedStatementService
from app.services.simple_statement_service import SimpleStatementService
from app.services.new_statement_service import NewStatementService
from app.services.category_service import CategoryService
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter()

@router.post("/upload", response_model=StatementSchema)
async def upload_statement(
    file: UploadFile = File(...),
    card_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a bank statement (PDF only) - Enhanced with category validation"""
    
    # Validate user has minimum categories before upload
    try:
        EnhancedStatementService.validate_statement_upload(db, current_user.id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate file type - only PDF allowed
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = file.filename.split('.')[-1].lower()
    filename = f"{current_user.id}_{timestamp}.{file_extension}"
    file_path = os.path.join(upload_dir, filename)
    
    # Save file
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}"
        )
    
    # Create statement record
    statement = Statement(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        file_type=file_extension,
        status="uploaded"
    )
    
    db.add(statement)
    db.commit()
    db.refresh(statement)
    
    return statement

@router.get("/", response_model=List[StatementSchema])
async def get_statements(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all statements for the current user"""
    statements = db.query(Statement).filter(Statement.user_id == current_user.id).all()
    return statements

@router.post("/{statement_id}/process", response_model=StatementProcess)
async def process_statement(
    statement_id: uuid.UUID,
    request: StatementProcessRequest = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Process a statement and extract transactions with AI insights"""
    # Get statement
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()
    
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found"
        )
    
    # Find card by ID or name
    card = None
    if request.card_id:
        card = db.query(Card).filter(
            Card.id == request.card_id,
            Card.user_id == current_user.id
        ).first()
    elif request.card_name:
        card = db.query(Card).filter(
            Card.card_name == request.card_name,
            Card.user_id == current_user.id
        ).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either card_id or card_name must be provided"
        )
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Parse statement
    try:
        statement.status = "processing"
        if request.statement_month:
            statement.statement_month = request.statement_month
        db.commit()
        
        # Get allowed categories for AI processing
        from app.services.category_service import CategoryService
        allowed_categories = CategoryService.get_category_names_for_ai(db, current_user.id)
        
        parser = StatementParser()
        
        with open(statement.file_path, "rb") as f:
            file_content = f.read()
        
        if statement.file_type == "csv":
            transactions_data = parser.parse_csv_statement(file_content)
            detected_period = None
        else:  # pdf
            transactions_data, detected_period = parser.parse_pdf_statement(file_content, allowed_categories)
            
        # Use detected period if not provided by user
        if detected_period and not request.statement_month:
            try:
                statement.statement_month = datetime.strptime(detected_period + "-01", "%Y-%m-%d").date()
                request.statement_month = statement.statement_month
            except ValueError:
                pass  # Use user-provided or default to None
        
        # Get user's transaction history for AI analysis
        user_history = db.query(Transaction).join(Card).filter(
            Card.user_id == current_user.id
        ).order_by(Transaction.transaction_date.desc()).limit(100).all()
        
        history_data = [
            {
                "merchant": tx.merchant,
                "amount": float(tx.amount),
                "currency": getattr(tx, 'currency', 'USD'),
                "category": tx.category,
                "date": tx.transaction_date.isoformat(),
                "description": tx.description
            }
            for tx in user_history
        ]
        
        # Create transactions using keyword-only categorization
        from app.services.category_service import CategoryService
        transactions_created = 0
        
        for tx_data in transactions_data:
            # Use keyword-based categorization instead of AI
            keyword_result = CategoryService.categorize_by_keywords(
                db, 
                current_user.id, 
                tx_data["merchant"]
            )
            
            # Determine category and confidence
            if keyword_result:
                category = keyword_result.category_name
                confidence = keyword_result.confidence
            else:
                category = "Sin categoría"  # Default uncategorized category
                confidence = 0.0
            
            transaction = Transaction(
                card_id=card.id,
                merchant=tx_data["merchant"],
                amount=tx_data["amount"],
                currency=tx_data.get("currency", "USD"),
                category=category,
                transaction_date=tx_data["transaction_date"],
                description=tx_data.get("description"),
                ai_confidence=confidence  # Store keyword confidence
            )
            
            db.add(transaction)
            transactions_created += 1
        
        # Generate AI insights for the statement (keep AI insights functionality)
        ai_service = AIService()
        statement_month_str = request.statement_month.strftime("%Y-%m") if request.statement_month else datetime.now().strftime("%Y-%m")
        ai_insights = ai_service.analyze_statement_and_generate_insights(
            transactions_data,
            statement_month_str,
            history_data
        )
        
        # Generate AI insights for the statement
        statement_month_str = request.statement_month.strftime("%Y-%m") if request.statement_month else datetime.now().strftime("%Y-%m")
        ai_insights = ai_service.analyze_statement_and_generate_insights(
            transactions_data,
            statement_month_str,
            history_data
        )
        
        # Update statement with insights
        statement.status = "processed"
        statement.is_processed = True
        statement.ai_insights = json.dumps(ai_insights)
        
        # Create alerts from AI insights
        alerts_created = 0
        
        # Create alerts from the alerts section
        for alert_data in ai_insights.get("alerts", []):
            try:
                # Map AI alert types to our enum
                alert_type_mapping = {
                    "unusual_spending": AlertType.UNUSUAL_SPENDING,
                    "large_transaction": AlertType.LARGE_TRANSACTION,
                    "new_merchant": AlertType.NEW_MERCHANT,
                    "budget_exceeded": AlertType.BUDGET_EXCEEDED
                }
                
                alert_type = alert_type_mapping.get(
                    alert_data.get("type", "unusual_spending"),
                    AlertType.UNUSUAL_SPENDING
                )
                
                # Map severity
                severity_mapping = {
                    "high": AlertSeverity.HIGH,
                    "medium": AlertSeverity.MEDIUM,
                    "low": AlertSeverity.LOW
                }
                
                severity = severity_mapping.get(
                    alert_data.get("severity", "medium"),
                    AlertSeverity.MEDIUM
                )
                
                alert = Alert(
                    user_id=current_user.id,
                    statement_id=statement_id,
                    alert_type=alert_type,
                    severity=severity,
                    title=alert_data.get("title", "Financial Alert"),
                    description=alert_data.get("description", ""),
                    criteria=json.dumps(alert_data.get("transaction_details", {}))
                )
                
                db.add(alert)
                alerts_created += 1
            except Exception as e:
                continue  # Skip problematic alerts
        
        # Create future monitoring alerts
        for monitor_data in ai_insights.get("future_monitoring", []):
            try:
                alert_type_mapping = {
                    "spending_limit": AlertType.SPENDING_LIMIT,
                    "merchant_watch": AlertType.MERCHANT_WATCH,
                    "category_budget": AlertType.CATEGORY_BUDGET
                }
                
                alert_type = alert_type_mapping.get(
                    monitor_data.get("alert_type", "spending_limit"),
                    AlertType.SPENDING_LIMIT
                )
                
                alert = Alert(
                    user_id=current_user.id,
                    statement_id=statement_id,
                    alert_type=alert_type,
                    severity=AlertSeverity.MEDIUM,
                    title=f"Monitor: {monitor_data.get('alert_type', 'Spending')}",
                    description=monitor_data.get("description", ""),
                    criteria=monitor_data.get("criteria", ""),
                    threshold=monitor_data.get("threshold"),
                    frequency=monitor_data.get("frequency", "monthly")
                )
                
                db.add(alert)
                alerts_created += 1
            except Exception as e:
                continue  # Skip problematic monitoring alerts
        
        db.commit()
        
        return StatementProcess(
            statement_id=statement_id,
            transactions_found=len(transactions_data),
            transactions_created=transactions_created,
            ai_insights=ai_insights,
            alerts_created=alerts_created
        )
        
    except Exception as e:
        statement.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing statement: {str(e)}"
        )

@router.get("/{statement_id}/insights")
async def get_statement_insights(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI insights for a processed statement"""
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()
    
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found"
        )
    
    if not statement.is_processed or not statement.ai_insights:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Statement has not been processed or has no insights"
        )
    
    try:
        insights = json.loads(statement.ai_insights)
        return insights
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error parsing insights data"
        )

# Enhanced Statement Processing Endpoints

@router.get("/{statement_id}/status", response_model=StatementStatusResponse)
async def get_statement_status(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed status for statement processing (for polling)"""
    try:
        status_data = EnhancedStatementService.get_statement_status(db, statement_id)
        return status_data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{statement_id}/extract", response_model=ExtractionResponse)
async def extract_transactions(
    statement_id: uuid.UUID,
    request: ExtractionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Extract transactions from uploaded statement (Step 1)"""
    try:
        # Convert statement_month from date to string if provided
        statement_month_str = None
        if request.statement_month:
            statement_month_str = request.statement_month.strftime("%Y-%m-%d")
        
        result = EnhancedStatementService.extract_transactions(
            db=db,
            statement_id=statement_id,
            card_id=request.card_id,
            card_name=request.card_name,
            statement_month=statement_month_str
        )
        return result
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/{statement_id}/categorize", response_model=CategorizationResponse)
async def categorize_transactions(
    statement_id: uuid.UUID,
    request: CategorizationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Categorize extracted transactions (Step 2)"""
    try:
        result = EnhancedStatementService.categorize_transactions(
            db=db,
            statement_id=statement_id,
            use_ai=request.use_ai,
            use_keywords=request.use_keywords
        )
        return result
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Categorization failed: {str(e)}")


@router.post("/{statement_id}/retry")
async def retry_processing_step(
    statement_id: uuid.UUID,
    request: RetryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retry a failed extraction or categorization step"""
    try:
        if request.step == "extraction":
            result = EnhancedStatementService.retry_step(
                db=db,
                statement_id=statement_id,
                step="extraction"
            )
        elif request.step == "categorization":
            result = EnhancedStatementService.retry_step(
                db=db,
                statement_id=statement_id,
                step="categorization",
                use_ai=True,
                use_keywords=True
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid step. Must be 'extraction' or 'categorization'")
        
        return result
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)}")


@router.get("/check-categories")
async def check_category_requirements(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if user meets category requirements for statement upload"""
    is_valid = CategoryService.validate_minimum_categories(db=db, user_id=current_user.id)
    count = CategoryService.get_category_count(db=db, user_id=current_user.id)
    
    return {
        "can_upload": is_valid,
        "current_categories": count,
        "minimum_required": 5,
        "message": "Ready to upload statements" if is_valid else f"Please create {5 - count} more categories before uploading statements"
    }

@router.post("/{statement_id}/simple-extract")
async def simple_extract_transactions(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Simple extraction endpoint that bypasses the enhanced service"""
    try:
        # Get statement using simple query
        statement_query = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement_query:
            raise HTTPException(status_code=404, detail="Statement not found")
        
        # Extract the actual values to avoid Column object issues
        file_path = str(statement_query.file_path)
        file_type = str(statement_query.file_type)
        user_id = statement_query.user_id
        filename = str(statement_query.filename)
        
        # Get allowed categories for AI processing
        from app.services.category_service import CategoryService
        allowed_categories = CategoryService.get_category_names_for_ai(db, user_id)
        
        # Parse the statement file using the statement parser directly
        parser = StatementParser()
        
        if file_type.lower() == 'pdf':
            transactions_data = parser.parse_pdf(file_path, allowed_categories)
        elif file_type.lower() == 'csv':
            transactions_data = parser.parse_csv(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
        
        if not transactions_data:
            raise HTTPException(status_code=400, detail="No transactions found in statement")
        
        # Create a simple card for testing
        card = Card(
            user_id=user_id,
            card_name="Test Card",
            card_type="credit",
            last_four_digits="0000",
            is_active=True
        )
        db.add(card)
        db.commit()
        db.refresh(card)
        
        # Create transactions
        created_transactions = []
        for trans_data in transactions_data:
            transaction = Transaction(
                card_id=card.id,
                merchant=trans_data.get('merchant', 'Unknown'),
                amount=trans_data.get('amount', 0.0),
                currency=trans_data.get('currency', 'USD'),
                transaction_date=trans_data.get('transaction_date'),
                description=trans_data.get('description', ''),
                category=None
            )
            created_transactions.append(transaction)
        
        db.add_all(created_transactions)
        db.commit()
        
        return {
            "statement_id": statement_id,
            "transactions_found": len(created_transactions),
            "card_id": card.id,
            "status": "success",
            "message": f"Successfully extracted {len(created_transactions)} transactions"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@router.post("/process-new")
async def process_statement_new_approach(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    New simplified approach: Upload and process statement in one step
    Extract + Categorize using predefined Spanish categories
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDF files are supported"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Process with new approach
        from app.services.new_statement_service import NewStatementService
        
        # Process with new approach (await the async static method)
        statement = await NewStatementService.process_statement_new_approach(
            db=db,
            user_id=str(current_user.id), 
            file_content=file_content,
            filename=file.filename
        )
        
        # Convert Statement object to JSON response
        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "file_type": statement.file_type,
            "status": statement.status,
            "user_id": str(statement.user_id),
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Statement processing failed: {str(e)}"
        )


@router.post("/upload-simple")
async def upload_statement_simple(
    file: UploadFile = File(...),
    card_id: str = Form(...),  # Require card selection for bank type detection
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload and process a bank statement with pattern-based extraction + AI categorization"""
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Get the selected card to determine bank type
    try:
        card = db.query(Card).filter(
            Card.id == card_id,
            Card.user_id == current_user.id
        ).first()
        
        if not card:
            raise HTTPException(
                status_code=404,
                detail="Selected card not found"
            )
        
        # Determine bank type from card's bank provider
        bank_type = "BCP"  # Default fallback
        if card.bank_provider:
            bank_short_name = card.bank_provider.short_name or card.bank_provider.name
            if "DINERS" in bank_short_name.upper():
                bank_type = "DINERS"
            elif "BCP" in bank_short_name.upper():
                bank_type = "BCP"
            # Add more bank mappings as needed
            
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing card information: {str(e)}"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Use the user's extraction script for accurate transaction extraction
        import tempfile
        import os
        from app.services.extraction_script import process_bank_statement_pdf
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            # Extract transactions using the user's proven script with bank type
            raw_transactions = process_bank_statement_pdf(temp_file_path, bank_type)
            
            if not raw_transactions:
                raise HTTPException(status_code=400, detail=f"No transactions found in PDF for {bank_type} format")
            
            # Convert transaction format for database storage
            # The script returns: transaction_date, description, transaction_type, currency, amount
            # We need to add categories and merchant names
            
            # Get user's categories for keyword-based categorization
            from app.services.category_service import CategoryService
            user_categories = CategoryService.get_category_names_for_ai(db, current_user.id)
            if not user_categories:
                user_categories = ['Supermercado', 'Entretenimiento', 'Combustible', 'Salud', 'Sin categoría']
            
            # Use keyword-based categorization instead of simple rules
            def keyword_categorize(description: str) -> str:
                keyword_result = CategoryService.categorize_by_keywords(
                    db, 
                    current_user.id, 
                    description
                )
                
                if keyword_result:
                    return keyword_result.category_name
                else:
                    return 'Sin categoría'  # Default uncategorized category
            
            # Process each transaction
            processed_transactions = []
            for tx in raw_transactions:
                processed_tx = {
                    'transaction_date': tx['transaction_date'],
                    'description': tx['description'],
                    'merchant': tx['description'],  # Use description as merchant
                    'amount': tx['amount'],
                    'currency': tx['currency'],
                    'category': keyword_categorize(tx['description']),
                    'transaction_type': tx['transaction_type']
                }
                processed_transactions.append(processed_tx)
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
        

        
        # Create statement record
        statement = Statement(
            id=uuid.uuid4(),
            user_id=current_user.id,
            filename=file.filename,
            file_path=f"temp/{file.filename}",
            file_type="pdf",
            status="completed",
            extraction_status="completed", 
            categorization_status="completed",
            is_processed=True,
            created_at=datetime.utcnow()
        )
        
        db.add(statement)
        db.commit()
        db.refresh(statement)
        
        # Get or create default card
        # Use the selected card instead of creating a new one
        selected_card = card  # We already have the card from earlier validation
        
        # Create transaction records
        created_transactions = []
        for txn_data in processed_transactions:
            try:
                # Parse transaction date if it's a string
                if isinstance(txn_data.get('transaction_date'), str):
                    transaction_date = datetime.strptime(txn_data['transaction_date'], '%Y-%m-%d').date()
                else:
                    transaction_date = txn_data.get('transaction_date')
                
                transaction = Transaction(
                    card_id=selected_card.id,
                    statement_id=statement.id,
                    merchant=txn_data.get('merchant', txn_data.get('description', 'Unknown')),
                    amount=float(txn_data.get('amount', 0)),
                    currency=txn_data.get('currency', 'USD'),
                    category=txn_data.get('category', 'Misc'),
                    transaction_date=transaction_date,
                    description=txn_data.get('description', txn_data.get('merchant', '')),
                    ai_confidence=0.90  # High confidence for pattern + AI
                )
                
                db.add(transaction)
                created_transactions.append(transaction)
                
            except Exception as e:
                logger.warning(f"Error creating transaction: {e}")
                continue
        
        # Store as JSON for compatibility
        statement.processed_transactions = json.dumps([
            {
                "description": txn.description,
                "amount": float(txn.amount),
                "currency": txn.currency,
                "category": txn.category,
                "transaction_date": txn.transaction_date.isoformat(),
            }
            for txn in created_transactions
        ])
        
        # Final commit
        db.commit()
        db.refresh(statement)
        

        

        
        # Return proper JSON response
        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "file_type": statement.file_type,
            "file_path": statement.file_path,
            "status": statement.status,
            "extraction_status": statement.extraction_status,
            "categorization_status": statement.categorization_status,
            "retry_count": "{}",
            "is_processed": statement.is_processed,
            "transactions_found": len(created_transactions),
            "error_message": statement.error_message,
            "created_at": statement.created_at.isoformat() if statement.created_at else None,
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None,
            "user_id": str(statement.user_id)
        }
        
    except Exception as e:
        logger.error(f"Statement processing failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Statement processing failed: {str(e)}"
        )


@router.delete("/{statement_id}")
async def delete_statement(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a statement and all its associated transactions"""
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()
    
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found"
        )
    
    # Delete associated transactions first (if any)
    transactions_deleted = db.query(Transaction).filter(
        Transaction.statement_id == statement_id
    ).delete()
    
    # Delete the file from filesystem if it exists
    if statement.file_path and os.path.exists(statement.file_path):
        try:
            os.remove(statement.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {statement.file_path}: {str(e)}")
    
    # Delete the statement record
    db.delete(statement)
    db.commit()
    
    return {
        "message": "Statement deleted successfully",
        "transactions_deleted": transactions_deleted,
        "statement_id": str(statement_id)
    }

@router.post("/{statement_id}/recategorize", response_model=CategorizationResponse)
async def recategorize_statement_transactions(
    statement_id: uuid.UUID,
    request: CategorizationRequest = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Recategorize existing statement transactions based on updated keywords/categories"""
    try:
        # Check if statement exists and belongs to user
        statement = db.query(Statement).filter(
            Statement.id == statement_id,
            Statement.user_id == current_user.id
        ).first()
        
        if not statement:
            raise HTTPException(status_code=404, detail="Statement not found")
        
        # Get existing transactions for this statement
        transactions = db.query(Transaction).filter(
            Transaction.statement_id == statement_id
        ).all()
        
        if not transactions:
            raise HTTPException(status_code=400, detail="No transactions found for this statement")
        
        logger.info(f"Recategorizing {len(transactions)} transactions for statement {statement_id}")
        
        # Create an instance of KeywordOnlyStatementService and call the method
        from app.services.keyword_only_statement_service import KeywordOnlyStatementService
        
        service = KeywordOnlyStatementService(db)
        result = service.recategorize_statement_transactions(statement_id)
        
        # Extract results from the service response
        recategorization_summary = result.get("recategorization_summary", {})
        categorized_count = recategorization_summary.get("categorized", 0)
        uncategorized_count = recategorization_summary.get("uncategorized", 0)
        
        return CategorizationResponse(
            statement_id=str(statement_id),
            transactions_categorized=categorized_count,
            ai_categorized=0,  # We only use keywords for recategorization
            keyword_categorized=categorized_count,
            uncategorized=uncategorized_count,
            status="completed",
            message=f"Successfully recategorized {categorized_count} transactions"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Recategorization failed for statement {statement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recategorization failed: {str(e)}")
