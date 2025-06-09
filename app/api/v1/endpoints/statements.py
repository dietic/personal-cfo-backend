from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import json
# Fast processing endpoints for PersonalCFO
from datetime import datetime, date

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
from app.services.category_service import CategoryService
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter()

@router.post("/upload", response_model=StatementSchema)
async def upload_statement(
    file: UploadFile = File(...),
    card_id: uuid.UUID = None,
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
        
        parser = StatementParser()
        
        with open(statement.file_path, "rb") as f:
            file_content = f.read()
        
        if statement.file_type == "csv":
            transactions_data = parser.parse_csv_statement(file_content)
            detected_period = None
        else:  # pdf
            transactions_data, detected_period = parser.parse_pdf_statement(file_content)
            
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
        
        # Create transactions
        ai_service = AIService()
        transactions_created = 0
        
        for tx_data in transactions_data:
            # Auto-categorize transaction with currency support
            ai_result = ai_service.categorize_transaction(
                tx_data["merchant"],
                float(tx_data["amount"]),
                tx_data.get("description", ""),
                tx_data.get("currency", "USD")
            )
            
            transaction = Transaction(
                card_id=card.id,
                merchant=tx_data["merchant"],
                amount=tx_data["amount"],
                currency=tx_data.get("currency", "USD"),
                category=ai_result["category"],
                transaction_date=tx_data["transaction_date"],
                description=tx_data.get("description"),
                ai_confidence=ai_result["confidence"]
            )
            
            db.add(transaction)
            transactions_created += 1
        
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
        result = EnhancedStatementService.extract_transactions(
            db=db,
            statement_id=statement_id,
            card_id=request.card_id,
            card_name=request.card_name,
            statement_month=request.statement_month
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
