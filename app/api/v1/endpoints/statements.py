from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Form, BackgroundTasks
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
import uuid
import os
import json
import logging
import re
import asyncio
from pathlib import Path
# Fast processing endpoints for PersonalCFO
from datetime import datetime, date, timezone

logger = logging.getLogger(__name__)

from app.core.database import get_db, engine
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
    RetryRequest,
    PDFStatusResponse,
    UnlockPDFRequest,
    UnlockPDFResponse
)
from app.services.statement_parser import StatementParser
from app.services.ai_service import AIService
from app.services.enhanced_statement_service import EnhancedStatementService
from app.services.simple_statement_service import SimpleStatementService
from app.services.simplified_statement_service import SimplifiedStatementService
from app.services.universal_statement_service import UniversalStatementService
from app.services.pdf_service import PDFService
from app.services.category_service import CategoryService
from app.core.exceptions import ValidationError, NotFoundError, ProcessingError

router = APIRouter()

# Background processing function
def process_statement_background(
    statement_id: str,
    file_content: bytes,
    file_name: str,
    card_id: int,
    user_id: int,
    password: Optional[str] = None
):
    """Background task to process statement"""
    from app.services.clean_ai_extractor import CleanAIStatementExtractor  # Use clean extractor
    from app.models.statement import Statement
    from app.models.transaction import Transaction
    from app.models.card import Card
    import json

    # Create a new database session for the background task
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    logger.info(f"🔄 Starting background processing for statement {statement_id}")

    try:
        # Get statement from database
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            logger.error(f"❌ Statement {statement_id} not found in database")
            return

        # Update status to processing
        statement.status = "processing"
        statement.processing_message = "Extracting transactions..."
        db.commit()

        # Get card for bank type
        card = db.query(Card).filter(
            Card.id == card_id,
            Card.user_id == user_id
        ).first()

        if not card:
            statement.status = "failed"
            statement.processing_message = "Card not found"
            db.commit()
            logger.error(f"❌ Card {card_id} not found")
            return

        # Save file to the pre-defined path
        file_path = Path(statement.file_path)
        file_path.parent.mkdir(exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Initialize AI extractor with database session
        extractor = CleanAIStatementExtractor(db_session=db)

        # Set bank type for statement
        bank_name = card.bank_provider.short_name if card.bank_provider and card.bank_provider.short_name else "Unknown"
        statement.bank_type = bank_name
        db.commit()

        # Extract transactions using enhanced AI method
        logger.info(f"🤖 Starting enhanced AI extraction for {bank_name} statement")

        # Use the enhanced direct PDF extraction method (no text fallback)
        logger.info(f"🤖 About to call extractor.extract_transactions with {len(file_content)} bytes, user_id={str(user_id)}, password={'***' if password else 'None'}")
        transactions_data = extractor.extract_transactions(
            file_content,
            str(user_id),
            password
        )
        logger.info(f"📦 Extractor returned: {type(transactions_data)}, count: {len(transactions_data) if transactions_data else 'None'}")

        if not transactions_data:
            logger.error(f"❌ No transactions data returned from extractor")
            statement.status = "failed"
            statement.processing_message = "No transactions found or extraction failed"
            db.commit()
            logger.error(f"❌ No transactions extracted from statement {statement_id}")
            return

        # Process transactions
        created_transactions = []
        for i, transaction_data in enumerate(transactions_data):
            try:
                logger.info(f"📝 Creating transaction {i+1}: {transaction_data}")

                # Parse date properly
                date_str = transaction_data.get("date", "")
                if date_str:
                    # Convert "12May" format to proper date
                    from datetime import datetime
                    try:
                        # Try parsing formats like "12May"
                        parsed_date = datetime.strptime(f"{date_str}2024", "%d%b%Y").date()
                    except:
                        # Fallback to today's date if parsing fails
                        from datetime import date
                        parsed_date = date.today()
                        logger.warning(f"⚠️ Could not parse date '{date_str}', using today")
                else:
                    from datetime import date
                    parsed_date = date.today()
                    logger.warning(f"⚠️ No date provided, using today")

                transaction = Transaction(
                    transaction_date=parsed_date,
                    merchant=transaction_data.get("description", "Unknown"),
                    amount=float(transaction_data.get("amount", 0)),
                    currency=transaction_data.get("currency", "PEN"),
                    category=transaction_data.get("category"),
                    card_id=card_id,
                    statement_id=statement_id
                )
                created_transactions.append(transaction)
                logger.info(f"✅ Transaction {i+1} created successfully")

            except Exception as e:
                logger.error(f"❌ Failed to create transaction {i+1}: {str(e)}")
                logger.error(f"📋 Transaction data was: {transaction_data}")
                continue

        # Bulk insert transactions
        db.add_all(created_transactions)
        db.commit()

        # Update statement with success status
        statement.status = "completed"
        statement.processing_message = f"Successfully processed {len(created_transactions)} transactions"
        statement.transactions_count = len(created_transactions)
        db.commit()

        logger.info(f"✅ Successfully processed statement {statement_id} - {len(created_transactions)} transactions created")

        # Clean up uploaded file
        if file_path.exists():
            file_path.unlink()

    except Exception as e:
        logger.error(f"❌ Error processing statement {statement_id}: {str(e)}")
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if statement:
            statement.status = "failed"
            statement.processing_message = f"Processing failed: {str(e)}"
            db.commit()
    finally:
        db.close()


async def process_statement_background_async(
    statement_id: str,
    file_content: bytes,
    file_name: str,
    card_id: int,
    user_id: int,
    password: Optional[str] = None
):
    """Async background task to process statement - truly non-blocking"""
    from app.services.universal_statement_service import UniversalStatementService
    from app.models.statement import Statement
    from app.models.card import Card

    # Create a new database session for the background task
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    logger.info(f"🔄 Starting ASYNC background processing for statement {statement_id}")

    try:
        # Get statement from database
        statement = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement:
            logger.error(f"❌ Statement {statement_id} not found in database")
            return

        # Update status to processing
        statement.status = "processing"
        statement.extraction_status = "processing"
        statement.categorization_status = "processing"
        statement.processing_message = "Extracting and categorizing transactions..."
        db.commit()

        # Get card for bank type
        card = db.query(Card).filter(
            Card.id == card_id,
            Card.user_id == user_id
        ).first()

        if not card:
            statement.status = "failed"
            statement.extraction_status = "failed"
            statement.categorization_status = "failed"
            statement.processing_message = "Card not found"
            db.commit()
            logger.error(f"❌ Card {card_id} not found")
            return

        # Save file to the pre-defined path
        file_path = Path(statement.file_path)
        file_path.parent.mkdir(exist_ok=True)

        # Use asyncio.to_thread for file operations to avoid blocking
        await asyncio.to_thread(lambda: file_path.write_bytes(file_content))

        # Set bank type for statement
        bank_name = card.bank_provider.short_name if card.bank_provider and card.bank_provider.short_name else "Unknown"
        statement.bank_type = bank_name
        db.commit()

        # Use UniversalStatementService for extraction AND categorization
        logger.info(f"🤖 Starting extraction and categorization for {bank_name} statement")

        def run_universal_processing():
            service = UniversalStatementService(db)
            return service.process_statement(
                statement_id=uuid.UUID(statement_id),
                file_content=file_content,
                password=password,
                use_keyword_categorization=True  # Enable keyword categorization during extraction
            )

        # Run processing in thread pool to avoid blocking
        result = await asyncio.to_thread(run_universal_processing)

        logger.info(f"✅ Successfully processed statement {statement_id}")
        logger.info(f"📊 Extraction and categorization completed: {result['transactions_count']} transactions")

    except Exception as e:
        logger.error(f"❌ Error processing statement {statement_id}: {str(e)}")

        # Update statement with error status
        try:
            statement = db.query(Statement).filter(Statement.id == statement_id).first()
            if statement:
                statement.status = "failed"
                statement.extraction_status = "failed"
                statement.categorization_status = "failed"
                statement.processing_message = f"Processing failed: {str(e)}"
                db.commit()
        except Exception as db_error:
            logger.error(f"❌ Error updating statement status: {str(db_error)}")

    finally:
        db.close()
        logger.info(f"🏁 Async processing completed for statement {statement_id}")


@router.post("/upload-simple-async")
async def upload_statement_simple_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    card_id: str = Form(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload and process a bank statement with AI extraction in the background"""

    logger.info(f"🚀 ASYNC UPLOAD REQUEST - File: {file.filename}, Card: {card_id}, User: {current_user.email}")
    logger.info(f"🔐 Password provided: {'Yes' if password else 'No'}")

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Check if PDF is password protected (quick check)
        pdf_status = PDFService.validate_pdf_access(file_content)
        if pdf_status["encrypted"] and not pdf_status["accessible"]:
            if password:
                logger.info("PDF is encrypted, attempting to unlock with provided password")
                success, unlocked_content, error_message = PDFService.unlock_pdf(file_content, password)
                if not success:
                    raise HTTPException(
                        status_code=423,
                        detail=f"Invalid password or PDF cannot be unlocked: {error_message}"
                    )
                file_content = unlocked_content
            else:
                raise HTTPException(
                    status_code=423,
                    detail="PDF is password protected. Please provide the password."
                )

        # Create statement record immediately with "pending" status
        statement_id = str(uuid.uuid4())

        # Create temporary file path for the statement
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        unique_filename = f"{statement_id}_{file.filename}"
        file_path = upload_dir / unique_filename

        # Create statement record first (instant response)
        statement = Statement(
            id=statement_id,
            filename=file.filename,
            file_path=str(file_path),
            file_type="pdf",
            status="pending",  # Start with pending status
            extraction_status="pending",
            categorization_status="pending",
            extraction_retries=0,
            categorization_retries=0,
            max_retries=3,
            transactions_count=0,
            is_processed=False,
            user_id=current_user.id,
            created_at=datetime.now(timezone.utc)
        )

        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Queue background processing AFTER responding to user
        # Use asyncio to run in truly independent task
        import asyncio
        task = asyncio.create_task(
            process_statement_background_async(
                statement_id=statement_id,
                file_content=file_content,
                file_name=file.filename,
                card_id=card_id,
                user_id=current_user.id,
                password=password
            )
        )
        # Store task reference to prevent garbage collection
        task.add_done_callback(lambda t: None)

        logger.info(f"✅ Statement {statement_id} queued for background processing")

        # Return immediately with pending status (user gets instant response)
        return {
            "id": statement_id,
            "filename": file.filename,
            "file_type": "pdf",
            "status": "pending",
            "message": "Statement uploaded successfully. Processing in background...",
            "user_id": current_user.id,
            "created_at": statement.created_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue statement: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue statement: {str(e)}"
        )

@router.get("/status/{statement_id}")
async def get_statement_status(
    statement_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the processing status of a statement"""

    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()

    if not statement:
        raise HTTPException(
            status_code=404,
            detail="Statement not found"
        )

    return {
        "id": statement.id,
        "filename": statement.filename,
        "status": statement.status,
        "transactions_count": statement.transactions_count,
        "extraction_method": statement.extraction_method,
        "created_at": statement.created_at,
        "updated_at": statement.updated_at,
        "error_message": statement.error_message if statement.status == "failed" else None
    }

@router.post("/check-pdf", response_model=PDFStatusResponse)
async def check_pdf_accessibility(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if PDF is accessible or password-protected"""
    try:
        # Read file content
        file_content = await file.read()

        # Check PDF accessibility
        pdf_status = PDFService.validate_pdf_access(file_content)

        return PDFStatusResponse(
            filename=file.filename,
            encrypted=pdf_status["encrypted"],
            accessible=pdf_status["accessible"],
            needs_password=pdf_status["encrypted"] and not pdf_status["accessible"],
            error_message=pdf_status.get("error"),
            file_size=len(file_content)
        )

    except Exception as e:
        logger.error(f"PDF check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check PDF: {str(e)}"
        )

@router.post("/unlock-pdf", response_model=UnlockPDFResponse)
async def unlock_pdf_with_password(
    file: UploadFile = File(...),
    password: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Unlock a password-protected PDF and return the unlocked content"""
    try:
        # Read the uploaded file content
        file_content = await file.read()

        # Try to unlock with provided password
        success, unlocked_content, error_message = PDFService.unlock_pdf(file_content, password)

        if not success:
            raise HTTPException(
                status_code=423,  # Locked
                detail=f"Invalid password or PDF cannot be unlocked: {error_message}"
            )

        logger.info(f"PDF successfully unlocked, content size: {len(unlocked_content)} bytes")
        return UnlockPDFResponse(
            success=True,
            message="PDF successfully unlocked"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF unlock failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unlock PDF: {str(e)}"
        )

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
    """Process a statement using AI extraction (unified approach)"""
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

    # Process statement using AI extraction
    try:
        statement.status = "processing"
        if request.statement_month:
            statement.statement_month = request.statement_month
        db.commit()

        # Read file content for AI processing
        with open(statement.file_path, "rb") as f:
            file_content = f.read()

        # Use AI-powered Universal Statement Service for extraction
        service = UniversalStatementService(db)

        result = service.process_statement(
            statement_id=statement.id,
            file_content=file_content,
            password=None,  # Can be enhanced later to support passwords
            use_keyword_categorization=True
        )

        # Update card association for all created transactions
        created_transactions = db.query(Transaction).filter(
            Transaction.statement_id == statement.id
        ).all()

        for transaction in created_transactions:
            transaction.card_id = card.id

        db.commit()

        # Return success response
        return StatementProcess(
            statement_id=statement.id,
            transactions_count=result["transactions_count"],
            status=result["status"],
            extraction_method="ai",
            categorization_method="keyword",
            message=f"Successfully processed {result['transactions_count']} transactions using AI extraction"
        )

    except ValidationError as e:
        statement.status = "error"
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except ProcessingError as e:
        statement.status = "error"
        db.commit()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Statement processing failed: {str(e)}")
        statement.status = "error"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )

@router.post("/process-new")
async def process_statement_new_approach(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    AI-powered statement processing: Upload and process statement in one step
    Extract + Categorize using AI extraction with keyword enhancement
    """
    # Validate file type (support both PDF and CSV now)
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.csv')):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and CSV files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Use Universal AI-powered service instead of legacy service
        from app.services.universal_statement_service import UniversalStatementService

        # Create statement record
        statement = Statement(
            id=uuid.uuid4(),
            user_id=current_user.id,
            filename=file.filename,
            file_path=f"ai_processed/{file.filename}",
            file_type="pdf" if file.filename.lower().endswith('.pdf') else "csv",
            status="processing",
            extraction_status="pending",
            categorization_status="pending",
            extraction_retries=0,
            categorization_retries=0,
            max_retries=3,
            is_processed=False,
            created_at=datetime.utcnow()
        )

        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Process with AI-powered Universal Service
        service = UniversalStatementService(db)

        result = service.process_statement(
            statement_id=statement.id,
            file_content=file_content,
            password=None,  # No password support in this endpoint
            use_keyword_categorization=True
        )

        # Convert Statement object to JSON response
        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "file_type": statement.file_type,
            "status": result["status"],
            "transactions_count": result["transactions_count"],
            "extraction_method": "ai",
            "user_id": str(statement.user_id),
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None,
            "message": f"Successfully processed {result['transactions_count']} transactions using AI extraction"
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"AI statement processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Statement processing failed: {str(e)}"
        )

@router.post("/upload-simple")
async def upload_statement_simple(
    file: UploadFile = File(...),
    card_id: str = Form(...),  # Require card selection for bank type detection
    password: Optional[str] = Form(None),  # Optional password for encrypted PDFs
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload and process a bank statement with AI extraction (supports password-protected PDFs)"""

    # DEBUG: Log that request was received
    logger.info(f"🚀 UPLOAD REQUEST RECEIVED - File: {file.filename}, Card: {card_id}, User: {current_user.email}")
    logger.info(f"🔐 Password provided: {'Yes' if password else 'No'}")

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Check if PDF is password protected
        pdf_status = PDFService.validate_pdf_access(file_content)
        if pdf_status["encrypted"] and not pdf_status["accessible"]:
            # If password provided, try to unlock the PDF
            if password:
                logger.info("PDF is encrypted, attempting to unlock with provided password")
                success, unlocked_content, error_message = PDFService.unlock_pdf(file_content, password)
                if not success:
                    raise HTTPException(
                        status_code=423,  # Locked
                        detail=f"Invalid password or PDF cannot be unlocked: {error_message}"
                    )
                # Use unlocked content for processing
                file_content = unlocked_content
                logger.info(f"PDF successfully unlocked, content size: {len(file_content)} bytes")
            else:
                raise HTTPException(
                    status_code=423,  # Locked status code
                    detail="PDF is password protected. Please provide password parameter."
                )

        # Get the selected card to determine bank type
        card = db.query(Card).filter(
            Card.id == card_id,
            Card.user_id == current_user.id
        ).first()

        if not card:
            raise HTTPException(
                status_code=404,
                detail="Selected card not found"
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing card information: {str(e)}"
        )

    try:
        # Use AI-powered Universal Statement Service instead of legacy extraction
        # Create statement record first
        statement = Statement(
            id=uuid.uuid4(),
            user_id=current_user.id,
            filename=file.filename,
            file_path=f"temp/{file.filename}",
            file_type="pdf",
            status="processing",
            extraction_status="in_progress",
            categorization_status="in_progress",
            is_processed=False,
            created_at=datetime.utcnow()
        )

        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Process with AI-powered Universal Service
        service = UniversalStatementService(db)

        result = service.process_statement(
            statement_id=statement.id,
            file_content=file_content,
            password=None,  # Password already used to unlock content above
            use_keyword_categorization=True
        )

        # Update card association for all created transactions
        # The UniversalStatementService creates transactions without card_id
        # We need to update them to associate with the selected card
        created_transactions = db.query(Transaction).filter(
            Transaction.statement_id == statement.id
        ).all()

        for transaction in created_transactions:
            transaction.card_id = card.id

        db.commit()

        # Return proper JSON response
        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "file_type": statement.file_type,
            "status": result["status"],
            "transactions_count": result["transactions_count"],
            "extraction_method": "ai",
            "user_id": str(statement.user_id),
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None,
            "message": f"Successfully processed {result['transactions_count']} transactions using AI extraction"
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Statement processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Statement processing failed: {str(e)}"
        )

@router.post("/upload-background")
async def upload_statement_background(
    file: UploadFile = File(...),
    card_id: str = Form(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload statement for background processing - returns immediately"""
    import base64
    from app.tasks.statement_tasks import process_statement_background

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Get card for bank type detection
        card = db.query(Card).filter(
            Card.id == card_id,
            Card.user_id == current_user.id
        ).first()

        if not card:
            raise HTTPException(
                status_code=404,
                detail="Card not found"
            )

        # Generate unique ID first
        statement_id = str(uuid.uuid4())

        # Save file content to uploads directory
        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, f"{statement_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create statement record with file_path set
        statement = Statement(
            id=statement_id,
            filename=file.filename,
            file_path=file_path,
            file_type="pdf",
            status="pending",
            processing_message="Queued for processing...",
            transactions_count=0,
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )

        db.add(statement)
        db.commit()

        # Encode file content for background task
        file_content_base64 = base64.b64encode(file_content).decode('utf-8')

        # Start background processing
        task = process_statement_background.delay(
            statement_id=str(statement.id),
            file_content_base64=file_content_base64,
            password=password
        )

        # Update statement with task ID
        statement.task_id = task.id
        db.commit()

        logger.info(f"🚀 Background task started for statement {statement.id} - Task ID: {task.id}")

        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "status": "pending",
            "task_id": task.id,
            "message": "Statement queued for processing. You can check the status or continue using the app.",
            "estimated_time": "2-4 minutes"
        }

    except Exception as e:
        logger.error(f"Failed to queue statement: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue statement: {str(e)}"
        )

@router.get("/{statement_id}/status")
async def get_statement_status(
    statement_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get processing status of a statement"""
    from app.core.celery_app import celery_app

    # Get statement
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()

    if not statement:
        raise HTTPException(
            status_code=404,
            detail="Statement not found"
        )

    # Get task status if task_id exists
    task_info = None
    if statement.task_id:
        try:
            task = celery_app.AsyncResult(statement.task_id)
            task_info = {
                "task_id": statement.task_id,
                "task_status": task.status,
                "task_info": task.info if task.info else {}
            }
        except Exception as e:
            logger.warning(f"Could not get task status: {str(e)}")

    return {
        "id": str(statement.id),
        "filename": statement.filename,
        "status": statement.status,
        "processing_message": statement.processing_message,
        "transactions_count": statement.transactions_count,
        "task_info": task_info,
        "created_at": statement.created_at.isoformat(),
        "updated_at": statement.updated_at.isoformat() if statement.updated_at else None
    }

@router.post("/process-ai")
async def process_statement_with_ai(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    use_keyword_enhancement: bool = Form(True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    AI-powered statement processing that can handle ANY bank format.
    This endpoint replaces bank-specific processing with universal AI extraction.
    """
    # Validate file type (support both PDF and CSV)
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.csv')):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and CSV files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Create statement record
        statement = Statement(
            id=uuid.uuid4(),
            user_id=current_user.id,
            filename=file.filename,
            file_path=f"ai_processed/{file.filename}",  # Virtual path
            file_type="pdf" if file.filename.lower().endswith('.pdf') else "csv",
            status="processing",
            extraction_status="pending",
            categorization_status="pending",
            extraction_retries=0,
            categorization_retries=0,
            max_retries=3,
            is_processed=False,
            created_at=datetime.utcnow()
        )

        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Process with Universal AI Service
        service = UniversalStatementService(db)

        result = service.process_statement(
            statement_id=statement.id,
            file_content=file_content,
            password=password,
            use_keyword_categorization=use_keyword_enhancement
        )

        return {
            "id": str(statement.id),
            "filename": statement.filename,
            "file_type": statement.file_type,
            "status": result["status"],
            "transactions_count": result["transactions_count"],
            "extraction_method": "ai",
            "keyword_enhancement": use_keyword_enhancement,
            "user_id": str(statement.user_id),
            "created_at": statement.created_at.isoformat(),
            "updated_at": statement.updated_at.isoformat() if statement.updated_at else None,
            "message": f"Successfully processed {result['transactions_count']} transactions using AI"
        }

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"AI statement processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Statement processing failed: {str(e)}"
        )

@router.post("/{statement_id}/simple-extract")
async def simple_extract_transactions(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """AI-powered extraction endpoint (unified approach)"""
    try:
        # Get statement using simple query
        statement_query = db.query(Statement).filter(Statement.id == statement_id).first()
        if not statement_query:
            raise HTTPException(status_code=404, detail="Statement not found")

        # Extract the actual values to avoid Column object issues
        file_path = str(statement_query.file_path)
        file_type = str(statement_query.file_type)
        user_id = statement_query.user_id

        # Read file content for AI processing
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Use AI-powered Universal Statement Service for extraction
        service = UniversalStatementService(db)

        result = service.process_statement(
            statement_id=statement_id,
            file_content=file_content,
            password=None,  # Can be enhanced later to support passwords
            use_keyword_categorization=True
        )

        return {
            "statement_id": statement_id,
            "transactions_count": result["transactions_count"],
            "status": result["status"],
            "extraction_method": "ai",
            "message": f"Successfully extracted {result['transactions_count']} transactions using AI"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@router.delete("/{statement_id}")
async def delete_statement(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a statement and its associated transactions"""
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()

    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found"
        )

    try:
        # Delete associated transactions first
        db.query(Transaction).filter(Transaction.statement_id == statement_id).delete()

        # Delete the statement
        db.delete(statement)
        db.commit()

        # Try to remove the physical file if it exists
        if statement.file_path and os.path.exists(statement.file_path):
            os.remove(statement.file_path)

        return {"message": "Statement deleted successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting statement {statement_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting statement: {str(e)}"
        )


@router.post("/{statement_id}/recategorize", response_model=CategorizationResponse)
async def recategorize_statement_transactions(
    statement_id: uuid.UUID,
    request: CategorizationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Recategorize existing transactions for a statement using keyword matching.
    This only applies categorization to existing transactions, does not re-extract.
    """
    # Verify statement exists and belongs to user
    statement = db.query(Statement).filter(
        Statement.id == statement_id,
        Statement.user_id == current_user.id
    ).first()

    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found"
        )

    try:
        # Get all transactions for this statement
        transactions = db.query(Transaction).filter(
            Transaction.statement_id == statement_id
        ).all()

        if not transactions:
            return CategorizationResponse(
                statement_id=str(statement_id),
                transactions_categorized=0,
                ai_categorized=0,
                keyword_categorized=0,
                uncategorized=0,
                status="completed",
                message="No transactions found to recategorize"
            )

        # Initialize categorization service
        from app.services.keyword_categorization_service import KeywordCategorizationService
        categorization_service = KeywordCategorizationService(db)

        # Counters
        keyword_categorized = 0
        uncategorized = 0

        # Apply keyword categorization to each transaction
        for transaction in transactions:
            # Try keyword categorization
            keyword_result = categorization_service.categorize_transaction(
                str(current_user.id),
                transaction.merchant,
                transaction.description or ""
            )

            if keyword_result and keyword_result.confidence > 0.0:
                # Apply keyword category
                transaction.category = keyword_result.category_name
                transaction.ai_confidence = keyword_result.confidence
                keyword_categorized += 1
                logger.info(f"Recategorized: {transaction.merchant} -> {keyword_result.category_name} (confidence: {keyword_result.confidence:.2f})")
            else:
                # Set to default category if no keyword match
                transaction.category = "Sin categoría"
                transaction.ai_confidence = 0.0
                uncategorized += 1

        # Update statement categorization status
        statement.categorization_status = "completed"

        # Commit all changes
        db.commit()

        total_categorized = keyword_categorized

        logger.info(f"Recategorization completed for statement {statement_id}: {keyword_categorized} keyword, {uncategorized} uncategorized")

        return CategorizationResponse(
            statement_id=str(statement_id),
            transactions_categorized=total_categorized,
            ai_categorized=0,  # This endpoint only does keyword categorization
            keyword_categorized=keyword_categorized,
            uncategorized=uncategorized,
            status="completed",
            message=f"Successfully recategorized {total_categorized} of {len(transactions)} transactions"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error recategorizing statement {statement_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recategorizing transactions: {str(e)}"
        )
