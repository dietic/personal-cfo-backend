from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import json
from datetime import datetime, date

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.card import Card
from app.schemas.statement import StatementCreate, Statement as StatementSchema, StatementProcess, StatementProcessRequest
from app.services.statement_parser import StatementParser
from app.services.ai_service import AIService

router = APIRouter()

@router.post("/upload", response_model=StatementSchema)
async def upload_statement(
    file: UploadFile = File(...),
    card_id: uuid.UUID = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a bank statement (PDF or CSV)"""
    # Validate file type
    if not file.filename.lower().endswith(('.pdf', '.csv')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and CSV files are supported"
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
        else:  # pdf
            transactions_data = parser.parse_pdf_statement(file_content)
        
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
        db.commit()
        
        return StatementProcess(
            statement_id=statement_id,
            transactions_found=len(transactions_data),
            transactions_created=transactions_created,
            ai_insights=ai_insights
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
