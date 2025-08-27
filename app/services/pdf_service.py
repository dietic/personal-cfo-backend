"""
Enhanced PDF Service for handling password-protected PDFs with multiple library fallbacks
"""

import io
import logging
from typing import Optional, Tuple, Dict, Any
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import pikepdf  # QPDF-backed

logger = logging.getLogger(__name__)


class PDFService:
    """Enhanced service for handling PDF operations with multiple library fallbacks"""

    @staticmethod
    def preprocess_pdf_content(file_content: bytes) -> bytes:
        """
        Preprocess PDF content to handle wrapped PDFs and fix corruption.
        
        This method handles PDFs that may be wrapped (e.g., with $BOP$/$EOP$ markers)
        by finding the real PDF content and extracting it properly.
        """
        logger.info("\n--- PDF Preprocessing ---")
        original_length = len(file_content)
        logger.info(f"Input size: {original_length} bytes")
        logger.info(f"First 100 bytes (hex): {file_content[:100].hex() if file_content else 'empty'}")
        logger.info(f"First 50 bytes (raw): {file_content[:50] if file_content else 'empty'}")
        
        # Check if this is a wrapped PDF (e.g., $BOP$ wrapper)
        if file_content.startswith(b'$BOP$'):
            logger.warning("⚠️ Found $BOP$ wrapper - this is a wrapped PDF")
            
            # Find the real PDF header
            pdf_start = file_content.find(b'%PDF-')
            if pdf_start > 0:
                logger.info(f"📍 Found real PDF header at offset {pdf_start}")
                
                # Find the end of the PDF (look for %%EOF or $EOP$)
                pdf_end = len(file_content)
                
                # Look for $EOP$ marker first
                eop_pos = file_content.find(b'$EOP$', pdf_start)
                if eop_pos > 0:
                    pdf_end = eop_pos
                    logger.info(f"📍 Found $EOP$ marker at offset {eop_pos}")
                
                # Also look for %%EOF
                eof_pos = file_content.rfind(b'%%EOF', pdf_start, pdf_end)
                if eof_pos > 0:
                    # Include the %%EOF marker
                    pdf_end = min(pdf_end, eof_pos + 5)
                    logger.info(f"📍 Found %%EOF at offset {eof_pos}")
                
                # Carve out the actual PDF content
                file_content = file_content[pdf_start:pdf_end]
                logger.info(f"✂️ Carved PDF: {original_length} bytes -> {len(file_content)} bytes")
                logger.info(f"Carved PDF first 50 bytes: {file_content[:50] if file_content else 'empty'}")
                logger.info(f"Carved PDF last 50 bytes: {file_content[-50:] if file_content else 'empty'}")
                logger.info("📋 Note: Letting PDF libraries handle xref table recovery automatically")
            else:
                logger.error("❌ $BOP$ wrapper found but no %PDF- header detected!")
        
        # If not wrapped but PDF header is not at the start, find and extract
        elif not file_content.startswith(b'%PDF-'):
            pdf_start = file_content.find(b'%PDF-')
            if pdf_start > 0 and pdf_start < 1024:  # Look in first 1KB
                logger.warning(f"⚠️ PDF header found at offset {pdf_start}, not at start")
                file_content = file_content[pdf_start:]
                logger.info(f"📍 Extracted from PDF header: {original_length} -> {len(file_content)} bytes")
            elif pdf_start < 0:
                logger.warning("❌ No valid PDF header found in file")
        else:
            logger.info("✅ PDF starts with valid header")
        
        # Now repair the PDF structure if needed
        if file_content.startswith(b'%PDF-'):
            file_content = PDFService._repair_pdf_structure(file_content)
        
        if len(file_content) != original_length:
            logger.info(f"✅ PDF preprocessing complete: {original_length} -> {len(file_content)} bytes")
        else:
            logger.info("No preprocessing changes needed")
            
        logger.info(f"Final first 20 bytes after preprocessing: {file_content[:20] if file_content else 'empty'}")
        logger.info("--- End Preprocessing ---\n")
        return file_content

    @staticmethod
    def _fix_xref_offsets(file_content: bytes, bytes_removed: int) -> bytes:
        """
        Fix xref table offsets after removing bytes from the beginning of the PDF.
        This is crucial for PDFs that were wrapped and had their prefixes removed.
        """
        logger.info(f"🔧 Starting xref offset fix - adjusting by -{bytes_removed} bytes")
        
        try:
            # Find the startxref location
            startxref_pos = file_content.rfind(b'startxref')
            if startxref_pos == -1:
                logger.warning("No 'startxref' found - cannot fix offsets")
                return file_content
            
            # Extract the current xref offset
            after_startxref = file_content[startxref_pos + 10:]  # Skip 'startxref\n'
            eof_pos = after_startxref.find(b'%%EOF')
            if eof_pos == -1:
                logger.warning("No '%%EOF' found after startxref - cannot fix offsets")
                return file_content
            
            current_offset_bytes = after_startxref[:eof_pos].strip()
            try:
                current_offset = int(current_offset_bytes)
                new_offset = current_offset - bytes_removed
                
                logger.info(f"📍 Found startxref at position {startxref_pos}")
                logger.info(f"📍 Current xref offset: {current_offset}")
                logger.info(f"📍 New xref offset: {new_offset}")
                
                if new_offset < 0:
                    logger.error(f"❌ Calculated negative offset {new_offset} - this indicates corruption")
                    return file_content
                
                # Replace the offset in the file
                new_offset_bytes = str(new_offset).encode('ascii')
                
                # Build the new content
                before_offset = file_content[:startxref_pos + 10]  # Up to and including 'startxref\n'
                after_offset = b'%%EOF' + file_content[startxref_pos + 10 + eof_pos + 5:]  # From %%EOF onwards
                
                fixed_content = before_offset + new_offset_bytes + b'\n' + after_offset
                
                logger.info(f"✅ Fixed xref offset: {current_offset} -> {new_offset}")
                logger.info(f"Fixed content size: {len(file_content)} -> {len(fixed_content)} bytes")
                
                return fixed_content
                
            except ValueError as e:
                logger.error(f"❌ Cannot parse xref offset '{current_offset_bytes}': {e}")
                return file_content
                
        except Exception as e:
            logger.error(f"❌ Error fixing xref offsets: {str(e)}")
            return file_content
    
    @staticmethod
    def _repair_pdf_structure(pdf_content: bytes) -> bytes:
        """
        Attempt to repair PDF structure, particularly xref issues.
        """
        try:
            # First, ensure the PDF ends with %%EOF if it doesn't
            if not pdf_content.endswith(b'%%EOF'):
                if b'%%EOF' in pdf_content:
                    # Find the last %%EOF and truncate there
                    eof_pos = pdf_content.rfind(b'%%EOF')
                    pdf_content = pdf_content[:eof_pos + 5]
                    logger.info("🔧 Truncated PDF at last %%EOF marker")
                else:
                    # Add %%EOF if completely missing
                    pdf_content = pdf_content + b'\n%%EOF'
                    logger.info("🔧 Added missing %%EOF marker")
            
            # Try to repair with pikepdf if available
            try:
                import pikepdf
                from io import BytesIO
                
                # Attempt to open and repair
                with pikepdf.open(BytesIO(pdf_content)) as pdf:
                    # Save to a new buffer with linearization
                    output = BytesIO()
                    pdf.save(output, linearize=True, compress_streams=False)
                    repaired_content = output.getvalue()
                    
                    if len(repaired_content) > 0:
                        logger.info(f"🔧 Repaired PDF with pikepdf: {len(pdf_content)} -> {len(repaired_content)} bytes")
                        return repaired_content
            except Exception as e:
                logger.debug(f"pikepdf repair attempt failed (non-critical): {e}")
            
            # If pikepdf fails, try PyMuPDF repair
            try:
                import fitz
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                if len(doc) > 0:
                    # Re-save the document to repair it
                    repaired_content = doc.tobytes(garbage=4, deflate=True)
                    doc.close()
                    if len(repaired_content) > 0:
                        logger.info(f"🔧 Repaired PDF with PyMuPDF: {len(pdf_content)} -> {len(repaired_content)} bytes")
                        return repaired_content
            except Exception as e:
                logger.debug(f"PyMuPDF repair attempt failed (non-critical): {e}")
                
        except Exception as e:
            logger.warning(f"PDF structure repair failed: {e}")
        
        return pdf_content

    @staticmethod
    def is_pdf_encrypted(file_content: bytes) -> bool:
        """
        Check if PDF is encrypted using multiple approaches.
        Returns True if ANY method detects encryption.
        """
        logger.info("\n--- PDF Encryption Check ---")
        logger.info(f"Original content size: {len(file_content)} bytes")
        
        # Preprocess content to fix common corruption issues
        file_content = PDFService.preprocess_pdf_content(file_content)
        logger.info(f"After preprocessing: {len(file_content)} bytes")
        
        # Track results from all methods
        methods_tried = []
        
        try:
            # Method 1: Try PyMuPDF first (most robust)
            doc = fitz.open(stream=file_content, filetype="pdf")
            is_encrypted = doc.needs_pass
            doc.close()
            methods_tried.append(f"PyMuPDF: {is_encrypted}")
            if is_encrypted:
                logger.info(f"PyMuPDF detected encryption: {is_encrypted}")
                return True
        except Exception as e:
            methods_tried.append(f"PyMuPDF: failed ({str(e)})")
            logger.warning(f"PyMuPDF encryption check failed: {str(e)}")

        try:
            # Method 2: Try PyPDF2
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            is_encrypted = pdf_reader.is_encrypted
            methods_tried.append(f"PyPDF2: {is_encrypted}")
            if is_encrypted:
                logger.info(f"PyPDF2 detected encryption: {is_encrypted}")
                return True
        except Exception as e:
            methods_tried.append(f"PyPDF2: failed ({str(e)})")
            logger.warning(f"PyPDF2 encryption check failed: {str(e)}")

        try:
            # Method 3: Try pdfplumber
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                # If we can open it without error, it's likely not encrypted
                # pdfplumber doesn't have direct encryption detection
                if hasattr(pdf, 'metadata') and pdf.metadata:
                    # Look for encryption in metadata
                    for value in pdf.metadata.values():
                        if value and 'encrypt' in str(value).lower():
                            methods_tried.append("pdfplumber: detected in metadata")
                            logger.info("pdfplumber detected encryption in metadata")
                            return True
            methods_tried.append("pdfplumber: no encryption detected")
        except Exception as e:
            methods_tried.append(f"pdfplumber: failed ({str(e)})")
            logger.warning(f"pdfplumber encryption check failed: {str(e)}")

        # Method 4: Manual detection as final fallback
        try:
            content_str = file_content.decode('latin-1', errors='ignore')
            encryption_indicators = [
                '/Encrypt',
                '/Filter /Standard',
                '/Filter/Standard',
                'endobj\n/Encrypt',
                '/O <',
                '/U <',
                '/CF',
                '/StdCF',
                '/SecurityHandler',
                '/R 4',
                '/R 5',
                '/R 6'
            ]

            for indicator in encryption_indicators:
                if indicator in content_str:
                    methods_tried.append(f"Manual: found '{indicator}'")
                    logger.info(f"Manual encryption detection: Found indicator '{indicator}'")
                    return True
            methods_tried.append("Manual: no indicators found")
        except Exception as e:
            methods_tried.append(f"Manual: failed ({str(e)})")
            logger.warning(f"Manual encryption detection failed: {str(e)}")

        # Log all methods tried for debugging
        logger.warning(f"No encryption detected by any method. Results: {'; '.join(methods_tried)}")
        return False

    @staticmethod
    def validate_pdf_access(file_content: bytes) -> Dict[str, Any]:
        """
        Validate if PDF can be accessed/read without password using multiple PDF libraries
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"PDF VALIDATION STARTED")
        logger.info(f"File size: {len(file_content)} bytes")
        logger.info(f"First 50 bytes (hex): {file_content[:50].hex() if file_content else 'empty'}")
        logger.info(f"First 20 bytes (raw): {file_content[:20] if file_content else 'empty'}")
        
        # Check if it looks like a PDF
        if file_content:
            if file_content.startswith(b'%PDF'):
                logger.info("✅ File starts with %PDF header")
            elif b'%PDF' in file_content[:1024]:
                pos = file_content[:1024].find(b'%PDF')
                logger.warning(f"⚠️ PDF header found at position {pos}, not at start")
            else:
                logger.error("❌ No PDF header found in first 1024 bytes")
                
            # Check for common wrappers
            if file_content.startswith(b'$BOP$'):
                logger.warning("⚠️ File starts with $BOP$ wrapper")
        
        result = {
            "encrypted": False,
            "accessible": False,
            "needs_password": False,
            "error": None
        }

        try:
            # Check if encrypted
            logger.info("Checking if PDF is encrypted...")
            is_encrypted = PDFService.is_pdf_encrypted(file_content)
            result["encrypted"] = is_encrypted
            logger.info(f"Encryption check result: encrypted={is_encrypted}")

            if not is_encrypted:
                # Test if we can actually read it
                logger.info("PDF not encrypted, testing readability...")
                readable = PDFService._test_pdf_readability(file_content)
                result["accessible"] = readable
                result["needs_password"] = not readable
                logger.info(f"Readability test result: readable={readable}")
                logger.info(f"Final validation result: {result}")
                logger.info(f"{'='*60}\n")
                return result

            # PDF is encrypted, test if accessible without password
            logger.info("PDF is encrypted, marking as needs password")
            result["accessible"] = False
            result["needs_password"] = True

        except Exception as e:
            result["error"] = f"PDF validation failed: {str(e)}"
            logger.error(f"PDF validation error: {str(e)}", exc_info=True)

        logger.info(f"Final validation result: {result}")
        logger.info(f"{'='*60}\n")
        return result

    @staticmethod
    def _test_pdf_readability(file_content: bytes) -> bool:
        """Test if PDF can be read using multiple libraries"""
        # Preprocess content to fix common corruption issues
        file_content = PDFService.preprocess_pdf_content(file_content)

        # Test with PyMuPDF
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            if len(doc) > 0:
                page = doc[0]
                page.get_text()  # Test if we can extract text
                doc.close()
                logger.info("PyMuPDF successfully read PDF")
                return True
        except Exception as e:
            logger.warning(f"PyMuPDF readability test failed: {str(e)}")

        # Test with pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                if len(pdf.pages) > 0:
                    logger.info("pdfplumber successfully read PDF")
                    return True
        except Exception as e:
            logger.warning(f"pdfplumber readability test failed: {str(e)}")

        # Test with PyPDF2
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            if len(pdf_reader.pages) > 0:
                logger.info("PyPDF2 successfully read PDF")
                return True
        except Exception as e:
            logger.warning(f"PyPDF2 readability test failed: {str(e)}")

        logger.warning("All PDF readability tests failed")
        return False

    @staticmethod
    def unlock_pdf(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """
        Attempt to unlock an encrypted PDF using multiple PDF libraries.
        Returns (success, unlocked_content, error_message)
        """
        logger.info(f"Attempting to unlock PDF with password length: {len(password)}")
        
        # Preprocess content to fix common corruption issues
        original_content = file_content
        file_content = PDFService.preprocess_pdf_content(file_content)

        # First check if it's actually encrypted
        if not PDFService.is_pdf_encrypted(original_content):
            logger.info("PDF is not encrypted, returning original content")
            return True, original_content, "PDF is not encrypted"

        # Method 1: Try PyMuPDF (most robust for problematic PDFs)
        logger.info("Trying PyMuPDF unlock...")
        success, content, error = PDFService._unlock_with_pymupdf(file_content, password)
        if success:
            logger.info("PyMuPDF unlock successful")
            return success, content, error
        else:
            logger.warning(f"PyMuPDF unlock failed: {error}")

        # Method 2: Try pikepdf (QPDF) to decrypt and rewrite bytes
        logger.info("Trying pikepdf (QPDF) unlock...")
        success, content, error = PDFService._unlock_with_pikepdf(file_content, password)
        if success:
            logger.info("pikepdf unlock successful")
            return success, content, error
        else:
            logger.warning(f"pikepdf unlock failed: {error}")

        # Method 3: Try PyPDF2 (fallback)
        logger.info("Trying PyPDF2 unlock...")
        success, content, error = PDFService._unlock_with_pypdf2(file_content, password)
        if success:
            logger.info("PyPDF2 unlock successful")
            return success, content, error
        else:
            logger.warning(f"PyPDF2 unlock failed: {error}")

        # Method 4: Try pdfplumber (alternative fallback)
        logger.info("Trying pdfplumber unlock...")
        success, content, error = PDFService._unlock_with_pdfplumber(file_content, password)
        if success:
            logger.info("pdfplumber unlock successful")
            return success, content, error
        else:
            logger.warning(f"pdfplumber unlock failed: {error}")

        # All methods failed
        final_error = f"Failed to unlock PDF with all available methods. This may indicate file corruption or an unsupported encryption method. Last error: {error}"
        logger.error(final_error)
        return False, b"", final_error

    @staticmethod
    def _unlock_with_pymupdf(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """Unlock PDF using PyMuPDF with authenticate() and strict validation."""
        try:
            # Open without password and authenticate if required
            doc = fitz.open(stream=file_content, filetype="pdf")
            try:
                if getattr(doc, "needs_pass", False):
                    if not doc.authenticate(password):
                        return False, b"", "Invalid password provided"
                # Export fully unencrypted bytes; prefer tobytes to avoid zero-page save issues
                try:
                    unlocked_content = doc.tobytes(encryption=fitz.PDF_ENCRYPT_NONE)
                except Exception as e:
                    # Last resort: copy pages one by one
                    try:
                        new_doc = fitz.open()
                        for i in range(len(doc)):
                            new_doc.insert_pdf(doc, from_page=i, to_page=i)
                        unlocked_content = new_doc.tobytes()
                        new_doc.close()
                    except Exception as ce:
                        return False, b"", f"PyMuPDF unlock failed: {str(ce)}"
            finally:
                doc.close()

            # Validate the produced bytes: reopen, must have pages and not require password
            try:
                vdoc = fitz.open(stream=unlocked_content, filetype="pdf")
                needs = getattr(vdoc, "needs_pass", False)
                pages = len(vdoc)
                vdoc.close()
                if needs:
                    return False, b"", "PyMuPDF unlock produced bytes that still require a password"
                if pages == 0:
                    return False, b"", "PyMuPDF unlock produced zero-page PDF"
            except Exception as ve:
                return False, b"", f"PyMuPDF unlock produced invalid bytes: {ve}"

            return True, unlocked_content, "PDF unlocked successfully with PyMuPDF"

        except Exception as e:
            logger.warning(f"PyMuPDF unlock failed: {str(e)}")
            return False, b"", f"PyMuPDF unlock failed: {str(e)}"

    @staticmethod
    def _unlock_with_pikepdf(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """Unlock PDF using pikepdf (QPDF) and return valid decrypted bytes with strict validation."""
        try:
            from io import BytesIO
            with pikepdf.open(BytesIO(file_content), password=password) as pdf:
                buf = BytesIO()
                # Save without specifying encryption to strip it entirely
                pdf.save(buf, linearize=True)
                unlocked_content = buf.getvalue()

            # Validate by reopening with PyMuPDF and ensuring not encrypted
            try:
                vdoc = fitz.open(stream=unlocked_content, filetype="pdf")
                needs = getattr(vdoc, "needs_pass", False)
                pages = len(vdoc)
                vdoc.close()
                if needs:
                    return False, b"", "pikepdf produced bytes that still require a password"
                if pages == 0:
                    return False, b"", "pikepdf produced zero-page PDF"
            except Exception as ve:
                return False, b"", f"pikepdf produced invalid bytes: {ve}"

            return True, unlocked_content, "PDF unlocked successfully with pikepdf"
        except pikepdf.PasswordError:
            return False, b"", "Invalid password provided"
        except Exception as e:
            return False, b"", f"pikepdf unlock failed: {e}"

    @staticmethod
    def _unlock_with_pypdf2(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """Unlock PDF using PyPDF2"""
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            if not pdf_reader.is_encrypted:
                # Build a clean, unencrypted copy
                pdf_writer = PyPDF2.PdfWriter()
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    pdf_writer.add_page(page)
                output_stream = io.BytesIO()
                pdf_writer.write(output_stream)
                unlocked_content = output_stream.getvalue()
                # Validate
                try:
                    vdoc = fitz.open(stream=unlocked_content, filetype="pdf")
                    needs = getattr(vdoc, "needs_pass", False)
                    pages = len(vdoc)
                    vdoc.close()
                    if needs or pages == 0:
                        return False, b"", "PyPDF2 pass-through produced invalid bytes"
                except Exception as ve:
                    return False, b"", f"PyPDF2 pass-through invalid bytes: {ve}"
                return True, unlocked_content, "PDF is not encrypted"

            # Attempt to decrypt with password
            decrypt_result = pdf_reader.decrypt(password)

            if decrypt_result == 0:
                return False, b"", "Incorrect password provided"
            elif decrypt_result == 1:
                # Successfully decrypted, create unlocked PDF
                pdf_writer = PyPDF2.PdfWriter()

                # Copy all pages to new PDF
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    pdf_writer.add_page(page)

                # Write to bytes
                output_stream = io.BytesIO()
                pdf_writer.write(output_stream)
                unlocked_content = output_stream.getvalue()

                # Validate
                try:
                    vdoc = fitz.open(stream=unlocked_content, filetype="pdf")
                    needs = getattr(vdoc, "needs_pass", False)
                    pages = len(vdoc)
                    vdoc.close()
                    if needs or pages == 0:
                        return False, b"", "PyPDF2 unlock produced invalid bytes"
                except Exception as ve:
                    return False, b"", f"PyPDF2 unlock invalid bytes: {ve}"

                return True, unlocked_content, "PDF unlocked successfully with PyPDF2"
            else:
                return False, b"", "Unknown decryption result"

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"PyPDF2 unlock failed: {error_msg}")

            if "incorrect startxref pointer" in error_msg.lower():
                return False, b"", "PDF has structural corruption that prevents PyPDF2 processing"
            elif "password" in error_msg.lower():
                return False, b"", "Invalid password provided"
            else:
                return False, b"", f"PyPDF2 unlock failed: {error_msg}"

    @staticmethod
    def _unlock_with_pdfplumber(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """Unlock PDF using pdfplumber (limited). Do not return encrypted bytes as success."""
        try:
            with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                if len(pdf.pages) > 0:
                    # We can open it with the password, but cannot emit decrypted bytes reliably
                    return False, b"", "pdfplumber opened with password but cannot produce decrypted bytes"
        except Exception as e:
            logger.warning(f"pdfplumber unlock failed: {str(e)}")
            return False, b"", f"pdfplumber unlock failed: {str(e)}"
        return False, b"", "pdfplumber could not open PDF with password"

    @staticmethod
    def extract_text_from_pdf(file_content: bytes, password: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Extract text content from a PDF file using multiple libraries

        Args:
            file_content: PDF file content as bytes
            password: Optional password if PDF is encrypted

        Returns:
            Tuple of (success: bool, text_content: Optional[str], error: Optional[str])
        """
        # 0) If a password is provided, first try to extract text directly with password (no unlock step)
        if password:
            # Try PyMuPDF by opening then authenticating
            try:
                doc = fitz.open(stream=file_content, filetype="pdf")
                if getattr(doc, "needs_pass", False):
                    if doc.authenticate(password):
                        page_count = len(doc)
                        text_content = ""
                        for page in doc:
                            try:
                                text_content += page.get_text() + "\n"
                            except Exception as pe:
                                logger.warning(f"PyMuPDF (authenticate) page text error: {pe}")
                        doc.close()
                        if text_content.strip():
                            logger.info(f"PyMuPDF (authenticate) extracted text: pages={page_count}, length={len(text_content)}")
                            return True, text_content, None
                    else:
                        logger.info("PyMuPDF authenticate() returned False with provided password")
                        doc.close()
                else:
                    # Not encrypted; proceed below without password
                    doc.close()
            except Exception as e:
                logger.warning(f"PyMuPDF text extraction with password failed: {str(e)}")

            # Try pdfplumber with password
            try:
                with pdfplumber.open(io.BytesIO(file_content), password=password) as pdf:
                    text_content = ""
                    for page in pdf.pages:
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text_content += page_text + "\n"
                        except Exception as pe:
                            logger.warning(f"pdfplumber (password) page text error: {pe}")
                    if text_content.strip():
                        logger.info(f"pdfplumber (password) extracted text: pages={len(pdf.pages)}, length={len(text_content)}")
                        return True, text_content, None
            except Exception as e:
                logger.warning(f"pdfplumber text extraction with password failed: {str(e)}")

            # Try PyPDF2 with password
            try:
                pdf_file = io.BytesIO(file_content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                if pdf_reader.is_encrypted:
                    decrypt_result = pdf_reader.decrypt(password)
                    if decrypt_result in (1, True):
                        text_content = ""
                        for page in pdf_reader.pages:
                            try:
                                page_text = page.extract_text()
                                if page_text:
                                    text_content += page_text + "\n"
                            except Exception as pe:
                                logger.warning(f"PyPDF2 (password) page text error: {pe}")
                        if text_content.strip():
                            logger.info(f"PyPDF2 (password) extracted text: pages={len(pdf_reader.pages)}, length={len(text_content)}")
                            return True, text_content, None
                    else:
                        logger.info("PyPDF2 decrypt() failed with provided password")
            except Exception as e:
                logger.warning(f"PyPDF2 text extraction with password failed: {str(e)}")

        # 1) If we got here and a password is provided, try to unlock to produce decrypted bytes
        if password:
            unlock_success, unlocked_content, unlock_error = PDFService.unlock_pdf(file_content, password)
            if unlock_success:
                file_content = unlocked_content
                # Safety: verify not encrypted
                try:
                    vdoc = fitz.open(stream=file_content, filetype="pdf")
                    if getattr(vdoc, "needs_pass", False):
                        vdoc.close()
                        return False, None, "Unlocked PDF still requires a password"
                    vdoc.close()
                except Exception as ve:
                    logger.warning(f"Post-unlock validation failed: {ve}")
            else:
                return False, None, f"Failed to unlock PDF: {unlock_error}"

        # 2) Try PyMuPDF without password (on unlocked or original content)
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            text_content = ""
            for page in doc:
                try:
                    text_content += page.get_text() + "\n"
                except Exception as pe:
                    logger.warning(f"PyMuPDF page text error: {pe}")
            page_count = len(doc)
            doc.close()

            if text_content.strip():
                logger.info(f"PyMuPDF extracted text: pages={page_count}, length={len(text_content)}")
                return True, text_content, None
        except Exception as e:
            logger.warning(f"PyMuPDF text extraction failed: {str(e)}")

        # 3) Try pdfplumber without password
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text_content = ""
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"
                    except Exception as pe:
                        logger.warning(f"pdfplumber page text error: {pe}")

                if text_content.strip():
                    logger.info(f"pdfplumber extracted text: pages={len(pdf.pages)}, length={len(text_content)}")
                    return True, text_content, None
        except Exception as e:
            logger.warning(f"pdfplumber text extraction failed: {str(e)}")

        # 4) Try PyPDF2 as last resort
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_content = ""

            for page in pdf_reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
                except Exception as pe:
                    logger.warning(f"PyPDF2 page text error: {pe}")

            if text_content.strip():
                logger.info(f"PyPDF2 extracted text: pages={len(pdf_reader.pages)}, length={len(text_content)}")
                return True, text_content, None
        except Exception as e:
            logger.warning(f"PyPDF2 text extraction failed: {str(e)}")

        return False, None, "Failed to extract text using all available PDF libraries"
