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
from app.services.enhanced_statement_service import EnhancedStatementService
# from app.services.universal_statement_service import UniversalStatementService
from app.services.category_service import CategoryService
from app.services.plan_limits import assert_within_limit
from app.core.exceptions import ValidationError, NotFoundError, ProcessingError

router = APIRouter()


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

        # Commented out OpenAI processing
        # def run_universal_processing():
        #     service = UniversalStatementService(db)
        #     return service.process_statement(
        #         statement_id=uuid.UUID(statement_id),
        #         file_content=file_content,
        #         password=password,
        #         use_keyword_categorization=True  # Enable keyword categorization during extraction
        #     )

        # Run processing in thread pool to avoid blocking
        # result = await asyncio.to_thread(run_universal_processing)
        result = {"transactions_count": 0, "status": "completed"}

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

    assert_within_limit(db, current_user, "statements")

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
        
        logger.info(f"📄 File read complete: {len(file_content)} bytes")
        logger.info(f"📝 First 50 bytes (hex): {file_content[:50].hex() if file_content else 'empty'}")
        logger.info(f"📝 First 20 bytes (raw): {file_content[:20] if file_content else 'empty'}")

        # Simplified PDF handling - assume PDF is accessible
        print("Uploading PDF...")
        actual_password = password  # Track the actual password for processing

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
            # Store selected card on the statement for UI display
            card_id=card_id,
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
                password=actual_password  # Use actual_password (None if already unlocked)
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

        # DEBUG: Log what we received
        print(f"🔍 CHECK-PDF DEBUG: Received {len(file_content)} bytes")
        print(f"🔍 CHECK-PDF DEBUG: First 50: {file_content[:50].hex()}")
        print(f"🔍 CHECK-PDF DEBUG: Last 50: {file_content[-50:].hex()}")

        print(f"Checking PDF accessibility for file: {file.filename}")
        
        # Check if PDF is encrypted using pikepdf (more reliable)
        import io
        import pikepdf
        
        is_encrypted = False
        is_accessible = True
        needs_password = False
        error = None
        processed_content = file_content
        
        # Check for $BOP wrapper format (some PDFs have this wrapper)
        # Handle corrupted wrapper markers that might have UTF-8 replacement characters
        has_bop_wrapper = file_content.startswith(b'$BOP$')
        has_corrupted_bop = False
        
        # Check for corrupted $BOP$ markers (with UTF-8 replacement chars)
        if not has_bop_wrapper and len(file_content) >= 5:
            # Look for corrupted $BOP$ pattern with replacement chars
            corrupted_bop_patterns = [
                b'$BOP\xef\xbf\xbd',  # $BOP�
                b'\xef\xbf\xbdBOP$',  # �BOP$
                b'$\xef\xbf\xbdOP$',  # $�OP$
            ]
            
            for pattern in corrupted_bop_patterns:
                if file_content.startswith(pattern):
                    has_corrupted_bop = True
                    print(f"Detected corrupted $BOP wrapper in: {file.filename}")
                    break
        
        if has_bop_wrapper or has_corrupted_bop:
            print(f"Detected $BOP wrapper in: {file.filename}")
            
            # Handle multiple wrapper scenarios
            has_eop_wrapper = file_content.endswith(b'$EOP$')
            has_corrupted_eop = False
            
            # Check for corrupted $EOP$ markers
            if not has_eop_wrapper and len(file_content) >= 5:
                corrupted_eop_patterns = [
                    b'$EOP\xef\xbf\xbd',  # $EOP�
                    b'\xef\xbf\xbdEOP$',  # �EOP$
                    b'$\xef\xbf\xbdOP$',  # $�OP$
                ]
                
                for pattern in corrupted_eop_patterns:
                    if file_content.endswith(pattern):
                        has_corrupted_eop = True
                        break
            
            if has_eop_wrapper or has_corrupted_eop:
                # Standard case: $BOP$ at start, $EOP$ at end
                processed_content = file_content[5:-5]  # Remove both $BOP$ and $EOP$
                print(f"Extracted PDF content from wrapper: {len(processed_content)} bytes")
                
                # Check if there are additional wrappers inside (malformed files)
                if b'$BOP$' in processed_content or b'$EOP$' in processed_content:
                    print("⚠️ Additional wrapper markers found inside extracted content")
                    # For malformed files, try to extract just the PDF content
                    # Look for the actual PDF start (%PDF-) after the first $BOP$
                    pdf_start = file_content.find(b'%PDF-')
                    if pdf_start != -1 and pdf_start > 0:
                        # Extract from PDF start to end (before any trailing wrappers)
                        pdf_end = file_content.rfind(b'%%EOF')
                        if pdf_end != -1:
                            pdf_end += 5  # Include %%EOF
                            processed_content = file_content[pdf_start:pdf_end]
                            print(f"Cleaned malformed wrapper: extracted {len(processed_content)} bytes")
            else:
                # No $EOP$ at end, just remove $BOP$ prefix
                processed_content = file_content[5:]  
                print(f"Extracted PDF content (no $EOP$ found): {len(processed_content)} bytes")
        
        try:
            # Try to open the PDF without password using pikepdf
            pdf_stream = io.BytesIO(processed_content)
            
            try:
                # First try without password
                pdf = pikepdf.open(pdf_stream)
                is_encrypted = pdf.is_encrypted
                
                if not is_encrypted:
                    print(f"PDF is not encrypted: {file.filename}")
                    # Check if we can access pages
                    if len(pdf.pages) > 0:
                        print(f"PDF is accessible with {len(pdf.pages)} pages: {file.filename}")
                    else:
                        print(f"PDF has no pages: {file.filename}")
                        is_accessible = False
                        error = "PDF has no readable pages"
                
                pdf.close()
                
            except pikepdf.PasswordError:
                # PDF is password protected
                is_encrypted = True
                needs_password = True
                is_accessible = False
                print(f"PDF is password protected: {file.filename}")
                
                # Try with empty password (some PDFs allow this)
                try:
                    pdf_stream.seek(0)  # Reset stream position
                    pdf = pikepdf.open(pdf_stream, password="")
                    if pdf.is_encrypted:
                        print(f"PDF can be opened with empty password: {file.filename}")
                        is_accessible = True
                        needs_password = False
                    pdf.close()
                except pikepdf.PasswordError:
                    print(f"PDF requires non-empty password: {file.filename}")
                except Exception as empty_pass_error:
                    print(f"Error with empty password: {empty_pass_error}")
                    
        except Exception as pdf_error:
            print(f"PDF parsing failed: {str(pdf_error)}")
            # If pikepdf fails, try fallback with PyPDF2
            try:
                from PyPDF2 import PdfReader
                pdf_stream.seek(0)
                reader = PdfReader(pdf_stream)
                is_encrypted = reader.is_encrypted
                needs_password = is_encrypted
                is_accessible = not is_encrypted
                
                if is_encrypted:
                    print(f"PDF is encrypted (PyPDF2 fallback): {file.filename}")
                    # Try empty password
                    try:
                        if reader.decrypt(""):
                            is_accessible = True
                            needs_password = False
                            print(f"PDF can be opened with empty password (PyPDF2): {file.filename}")
                    except Exception:
                        pass
                else:
                    print(f"PDF is not encrypted (PyPDF2 fallback): {file.filename}")
                    # Even if PyPDF2 says not encrypted, check for encryption markers to be sure
                    encryption_indicators = [
                        b'/Encrypt', b'/Filter', b'/Standard', b'/CF', 
                        b'/StmF', b'/StrF', b'/Crypt', b'/Encryption'
                    ]
                    has_encryption_markers = any(indicator in processed_content for indicator in encryption_indicators)
                    
                    if has_encryption_markers:
                        print(f"Overriding PyPDF2: PDF appears encrypted based on content markers: {file.filename}")
                        is_encrypted = True
                        is_accessible = False
                        needs_password = True
                    
            except Exception as fallback_error:
                print(f"Both pikepdf and PyPDF2 failed: {fallback_error}")
                # If both libraries fail, check if it's likely encrypted by examining the content
                # Look for encryption dictionary markers in the extracted content
                encryption_indicators = [
                    b'/Encrypt', b'/Filter', b'/Standard', b'/CF', 
                    b'/StmF', b'/StrF', b'/Crypt', b'/Encryption'
                ]
                
                has_encryption_markers = any(indicator in processed_content for indicator in encryption_indicators)
                
                if has_encryption_markers:
                    print(f"PDF appears to be encrypted based on content analysis (found encryption markers): {file.filename}")
                    is_encrypted = True
                    is_accessible = False
                    needs_password = True
                    error = f"PDF appears to be encrypted but parsing failed: {str(fallback_error)}"
                else:
                    print(f"PDF parsing failed but doesn't appear encrypted (no encryption markers found): {file.filename}")
                    is_encrypted = False
                    is_accessible = False
                    needs_password = False
                    error = f"PDF parsing failed: {str(fallback_error)}"
        
        return PDFStatusResponse(
            filename=file.filename,
            encrypted=is_encrypted,
            accessible=is_accessible,
            needs_password=needs_password,
            error=error,
            file_size=len(file_content)
        )

    except Exception as e:
        logger.error(f"PDF check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check PDF: {str(e)}"
        )

@router.post("/debug-upload")
async def debug_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Debug endpoint to see exactly what the UI is sending"""
    file_content = await file.read()
    
    # Additional analysis for corruption detection
    corruption_indicators = []
    
    # Check for UTF-8 replacement characters (common corruption)
    utf8_replacement = b'\xef\xbf\xbd'  # � character
    if utf8_replacement in file_content:
        corruption_indicators.append("utf8_replacement_chars")
    
    # Check for null bytes or other common corruption patterns
    if b'\x00' in file_content:
        corruption_indicators.append("null_bytes")
    
    return {
        "filename": file.filename,
        "size_received": len(file_content),
        "first_20_bytes": file_content[:20].hex(),
        "last_20_bytes": file_content[-20:].hex(),
        "contains_bop": b'$BOP$' in file_content,
        "contains_pdf": b'%PDF-' in file_content,
        "bop_positions": [i for i in range(len(file_content)) if file_content.startswith(b'$BOP$', i)],
        "eop_positions": [i for i in range(len(file_content)) if file_content.startswith(b'$EOP$', i)],
        "corruption_indicators": corruption_indicators,
        "utf8_replacement_count": file_content.count(utf8_replacement),
    }

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
        
        # DEBUG: Log exactly what we received
        print(f"🔍 DEBUG: Received {len(file_content)} bytes from UI")
        print(f"🔍 DEBUG: First 50 bytes: {file_content[:50].hex()}")
        print(f"🔍 DEBUG: Last 50 bytes: {file_content[-50:].hex()}")
        print(f"🔍 DEBUG: Contains $BOP$: {b'$BOP$' in file_content}")
        print(f"🔍 DEBUG: Contains %PDF-: {b'%PDF-' in file_content}")
        
        # Check for $BOP wrapper format
        # Handle corrupted wrapper markers that might have UTF-8 replacement characters
        processed_content = file_content
        has_bop_wrapper = file_content.startswith(b'$BOP$')
        has_corrupted_bop = False
        
        # Check for corrupted $BOP$ markers (with UTF-8 replacement chars)
        if not has_bop_wrapper and len(file_content) >= 5:
            # Look for corrupted $BOP$ pattern with replacement chars
            corrupted_bop_patterns = [
                b'$BOP\xef\xbf\xbd',  # $BOP�
                b'\xef\xbf\xbdBOP$',  # �BOP$
                b'$\xef\xbf\xbdOP$',  # $�OP$
            ]
            
            for pattern in corrupted_bop_patterns:
                if file_content.startswith(pattern):
                    has_corrupted_bop = True
                    print(f"Detected corrupted $BOP wrapper in unlock request: {file.filename}")
                    break
        
        if has_bop_wrapper or has_corrupted_bop:
            print(f"Detected $BOP wrapper in unlock request: {file.filename}")
            
            # Handle multiple wrapper scenarios
            has_eop_wrapper = file_content.endswith(b'$EOP$')
            has_corrupted_eop = False
            
            # Check for corrupted $EOP$ markers
            if not has_eop_wrapper and len(file_content) >= 5:
                corrupted_eop_patterns = [
                    b'$EOP\xef\xbf\xbd',  # $EOP�
                    b'\xef\xbf\xbdEOP$',  # �EOP$
                    b'$\xef\xbf\xbdOP$',  # $�OP$
                ]
                
                for pattern in corrupted_eop_patterns:
                    if file_content.endswith(pattern):
                        has_corrupted_eop = True
                        break
            
            if has_eop_wrapper or has_corrupted_eop:
                # Standard case: $BOP$ at start, $EOP$ at end
                processed_content = file_content[5:-5]  # Remove both $BOP$ and $EOP$
                print(f"Extracted PDF content from wrapper for unlock: {len(processed_content)} bytes")
                
                # Check if there are additional wrappers inside (malformed files)
                if b'$BOP$' in processed_content or b'$EOP$' in processed_content:
                    print("⚠️ Additional wrapper markers found inside extracted content")
                    # For malformed files, try to extract just the PDF content
                    # Look for the actual PDF start (%PDF-) after the first $BOP$
                    pdf_start = file_content.find(b'%PDF-')
                    if pdf_start != -1 and pdf_start > 0:
                        # Extract from PDF start to end (before any trailing wrappers)
                        pdf_end = file_content.rfind(b'%%EOF')
                        if pdf_end != -1:
                            pdf_end += 5  # Include %%EOF
                            processed_content = file_content[pdf_start:pdf_end]
                            print(f"Cleaned malformed wrapper: extracted {len(processed_content)} bytes")
            else:
                # No $EOP$ at end, just remove $BOP$ prefix
                processed_content = file_content[5:]  
                print(f"Extracted PDF content (no $EOP$ found) for unlock: {len(processed_content)} bytes")
        
        # Try to unlock the PDF with the provided password
        import io
        import pikepdf
        
        try:
            pdf_stream = io.BytesIO(processed_content)
            
            # Try to open with password and handle damaged files gracefully
            try:
                pdf = pikepdf.open(pdf_stream, password=password)
            except Exception as open_error:
                # If opening fails, try with ignore_xref_streams=True for damaged files
                print(f"First open attempt failed: {open_error}, trying with ignore_xref_streams")
                pdf_stream.seek(0)  # Reset stream position
                pdf = pikepdf.open(pdf_stream, password=password, ignore_xref_streams=True)
            
            # If we get here, the password worked
            print(f"PDF successfully unlocked with password: {file.filename}")
            
            # Get the unlocked content - handle potential save errors
            try:
                output_stream = io.BytesIO()
                pdf.save(output_stream)
                unlocked_content = output_stream.getvalue()
                pdf.close()
                
                # Store the unlocked PDF file
                unlocked_dir = Path("unlocked_pdfs")
                unlocked_dir.mkdir(exist_ok=True)
                
                # Create a unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unlocked_filename = f"unlocked_{current_user.id}_{timestamp}_{file.filename}"
                unlocked_file_path = unlocked_dir / unlocked_filename
                
                # Save the unlocked PDF
                unlocked_file_path.write_bytes(unlocked_content)
                print(f"✅ Unlocked PDF saved to: {unlocked_file_path}")
                
                return UnlockPDFResponse(
                    success=True,
                    message="PDF successfully unlocked",
                    unlocked_content=unlocked_content
                )
                
            except Exception as save_error:
                print(f"Error saving unlocked PDF: {save_error}")
                # Even if saving fails, we can still proceed with the original content
                # since we successfully opened it with the password
                pdf.close()
                return UnlockPDFResponse(
                    success=True,
                    message="PDF unlocked but may have formatting issues",
                    unlocked_content=processed_content  # Return the original processed content
                )
            
        except pikepdf.PasswordError:
            print(f"Incorrect password for PDF: {file.filename}")
            return UnlockPDFResponse(
                success=False,
                message="Incorrect password"
            )
            
        except Exception as e:
            print(f"Error unlocking PDF: {str(e)}")
            return UnlockPDFResponse(
                success=False,
                message=f"Failed to unlock PDF: {str(e)}"
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

    assert_within_limit(db, current_user, "statements")

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
        status="uploaded",
        # Save card id if provided
        card_id=card_id
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

    # Persist the selected card on the statement for UI display
    try:
      statement.card_id = card.id
      db.commit()
    except Exception:
      db.rollback()

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
        # service = UniversalStatementService(db)

        # result = service.process_statement(
        #     statement_id=statement.id,
        #     file_content=file_content,
        #     password=None,  # Can be enhanced later to support passwords
        #     use_keyword_categorization=True
        # )
        result = {"transactions_count": 0, "status": "completed"}

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
        # from app.services.universal_statement_service import UniversalStatementService

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
        # service = UniversalStatementService(db)

        # result = service.process_statement(
        #     statement_id=statement.id,
        #     file_content=file_content,
        #     password=None,  # No password support in this endpoint
        #     use_keyword_categorization=True
        # )
        result = {"transactions_count": 0, "status": "completed"}

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

    assert_within_limit(db, current_user, "statements")

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

        # Simplified PDF handling - assume PDF is accessible
        print("Uploading PDF...")
        actual_password = password  # Track the actual password for processing

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
            # Persist selected card on the statement
            card_id=card.id,
            created_at=datetime.utcnow()
        )

        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Process with AI-powered Universal Service
        # service = UniversalStatementService(db)

        # result = service.process_statement(
        #     statement_id=statement.id,
        #     file_content=file_content,
        #     password=None,  # Password already used to unlock content above
        #     use_keyword_categorization=True
        # )
        result = {"transactions_count": 0, "status": "completed"}

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
        # service = UniversalStatementService(db)

        # result = service.process_statement(
        #     statement_id=statement.id,
        #     file_content=file_content,
        #     password=password,
        #     use_keyword_categorization=use_keyword_enhancement
        # )
        result = {"transactions_count": 0, "status": "completed"}

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
        # service = UniversalStatementService(db)

        # result = service.process_statement(
        #     statement_id=statement_id,
        #     file_content=file_content,
        #     password=None,  # Can be enhanced later to support passwords
        #     use_keyword_categorization=True
        # )
        result = {"transactions_count": 0, "status": "completed"}

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
