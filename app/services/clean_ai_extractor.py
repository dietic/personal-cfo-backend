"""
Clean AI Statement Extractor - Universal bank statement processing

This service provides reliable extraction of bank statement transactions from any bank
using OpenAI GPT-4o with universal prompts and error handling.
"""

import logging
import openai
import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProcessingError
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)


class CleanAIStatementExtractor:
    """Universal AI Statement Extractor for any bank"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def extract_transactions(self, file_content: bytes, user_id: str, password: Optional[str] = None) -> List[Dict[str, Any]]:
        """Main extraction method for any bank statement"""
        logger.info(f"🔍 Using Universal Clean AI extraction (user: {user_id}, password provided: {password is not None})")
        logger.info(f"📄 PDF content size: {len(file_content)} bytes")

        try:
            transactions = self._extract_transactions_optimized(file_content, password)
            if not transactions or len(transactions) == 0:
                logger.warning("Primary text-based extraction returned no transactions, trying Vision fallback...")
                transactions = self._extract_transactions_via_vision(file_content, password)

            if not transactions or len(transactions) == 0:
                logger.error("❌ Universal AI extraction returned no transactions!")
                raise ProcessingError("AI extraction returned no transactions. Please try again.")

            logger.info(f"✅ Universal Clean AI extracted {len(transactions)} transactions")
            logger.info(f"📋 Sample transaction: {transactions[0] if transactions else 'None'}")
            return transactions

        except Exception as e:
            logger.error(f"❌ Universal Clean AI extraction failed: {str(e)}")
            import traceback
            logger.error(f"📝 Traceback: {traceback.format_exc()}")
            raise ProcessingError(f"AI extraction failed: {str(e)}. Please try again.")

    def _extract_transactions_optimized(self, file_content: bytes, password: Optional[str] = None) -> List[Dict[str, Any]]:
        """Universal extraction method for any bank statement"""
        try:
            logger.info("Processing PDF with universal AI extraction (text-based)...")

            # Extract text using centralized PDFService with robust unlock fallbacks
            success, full_text, err = PDFService.extract_text_from_pdf(file_content, password)
            if not success or not full_text or not full_text.strip():
                if err:
                    logger.error(err)
                else:
                    logger.error("No text extracted from PDF")
                return []

            # Create universal prompt for any bank statement
            prompt = f"""Extract ALL purchase transactions from this bank statement.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY actual purchases/transactions (merchant charges, purchases, payments)
2. EXCLUDE: fees, balance transfers, payments between accounts, adjustments, interests
3. Determine the statement period from the FIRST PAGE header (e.g., "Statement period", "Periodo", "Del ... al ..."). Use this to infer the CORRECT YEAR for each transaction date when the statement lists dates without a year.
4. For each transaction return these fields:
   - date: full ISO date in format YYYY-MM-DD (include the correct year inferred from the statement period; if the period spans months/years, use the appropriate year for each date)
   - description: complete merchant/transaction description as printed (preserve names, remove internal codes)
   - amount: numeric amount (positive number, use dot as decimal separator)
   - currency: currency code (PEN, USD, EUR, etc.)
5. Handle multiple currencies if present.
6. Return ONLY the JSON array with no additional text.

EXPECTED OUTPUT FORMAT - JSON array:
[
  {{
    "date": "2025-05-12",
    "description": "STARBUCKS LIMA CENTER",
    "amount": 25.50,
    "currency": "PEN"
  }}
]

STATEMENT CONTENT:
{full_text}

Extract ALL purchase transactions. Return ONLY the JSON array with no additional text."""

            # Make API request
            logger.info("Making OpenAI API request...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000,
                temperature=0.1
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"GPT-4o response: {len(content)} characters")

            # Parse JSON response
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_start = content.find('[')
                json_end = content.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                else:
                    logger.error("No JSON found in response")
                    return []

            transactions = json.loads(json_str)
            logger.info(f"✅ Successfully parsed {len(transactions)} transactions")

            # Transform to expected format for UniversalStatementService
            transformed_transactions = []
            for txn in transactions:
                # Parse date with full year (expecting ISO YYYY-MM-DD; try common fallbacks)
                date_str = txn.get("date", "").strip()
                if date_str:
                    try:
                        from datetime import datetime, date
                        parsed_date = None
                        # Try ISO first
                        try:
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except Exception:
                            pass
                        # Try common alternative formats if ISO fails
                        if not parsed_date:
                            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%d %B %Y"):
                                try:
                                    parsed_date = datetime.strptime(date_str, fmt).date()
                                    break
                                except Exception:
                                    continue
                        if not parsed_date:
                            # Last attempt: fromisoformat (may handle variants)
                            try:
                                parsed_date = datetime.fromisoformat(date_str).date()
                            except Exception:
                                parsed_date = date.today()
                                logger.warning(f"Could not parse date '{date_str}', defaulting to today")
                    except Exception:
                        from datetime import date
                        parsed_date = date.today()
                        logger.warning(f"Date parsing error for '{date_str}', defaulting to today")
                else:
                    from datetime import date
                    parsed_date = date.today()

                # Transform to expected field names
                transformed_txn = {
                    'merchant': txn.get('description', 'Unknown'),  # description -> merchant
                    'amount': float(txn.get('amount', 0)),
                    'currency': txn.get('currency', 'PEN'),
                    'transaction_date': parsed_date,  # parsed date object
                    'description': txn.get('description', 'Unknown'),  # keep original description
                    'category': txn.get('category', None)  # category if provided
                }
                transformed_transactions.append(transformed_txn)

            logger.info(f"🔄 Transformed {len(transformed_transactions)} transactions to expected format")
            return transformed_transactions

        except Exception as e:
            logger.error(f"Optimized extraction failed: {str(e)}")
            return []

    def _extract_transactions_via_vision(self, file_content: bytes, password: Optional[str]) -> List[Dict[str, Any]]:
        """Fallback using GPT-4o Vision by sending page images when text extraction fails."""
        try:
            import base64
            import io
            import fitz  # PyMuPDF

            # If password provided, unlock bytes using our service (includes pikepdf fallback)
            if password:
                success, unlocked, err = PDFService.unlock_pdf(file_content, password)
                if success:
                    file_content = unlocked
                else:
                    logger.warning(f"Vision fallback: unlock failed: {err}")
                    return []

            # Open PDF; if still fails, give up
            doc = fitz.open(stream=file_content, filetype="pdf")
            pages = len(doc)
            if pages == 0:
                doc.close()
                return []

            # Render first N pages to control token/cost
            MAX_PAGES = min(5, pages)
            images = []
            for i in range(MAX_PAGES):
                try:
                    page = doc.load_page(i)
                    pix = page.get_pixmap(dpi=144)  # balance clarity vs size
                    png_bytes = pix.tobytes("png")
                    b64 = base64.b64encode(png_bytes).decode("ascii")
                    images.append(f"data:image/png;base64,{b64}")
                except Exception as pe:
                    logger.warning(f"Vision fallback: render page {i} failed: {pe}")
                    continue
            doc.close()

            if not images:
                return []

            # Build multi-part content with text instructions + images
            content_parts: List[Dict[str, Any]] = []
            content_parts.append({"type": "text", "text": (
                "Extract ALL purchase transactions from these bank statement images.\n"
                "Return ONLY a JSON array of objects with: date (YYYY-MM-DD, infer year from context), \n"
                "description (merchant), amount (number, dot decimal), currency (code). Exclude fees/interests/transfers."
            )})
            for img in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img}
                })

            logger.info(f"Making OpenAI Vision request with {len(images)} page images...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content_parts}],
                max_tokens=8000,
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"GPT-4o Vision response: {len(content)} characters")

            # Parse JSON array from content
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_start = content.find('[')
                json_end = content.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                else:
                    logger.error("Vision fallback: No JSON found in response")
                    return []

            raw = json.loads(json_str)

            # Transform as in text path
            transformed: List[Dict[str, Any]] = []
            from datetime import datetime, date
            for txn in raw:
                date_str = (txn.get("date") or "").strip()
                parsed_date = None
                if date_str:
                    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%d %B %Y"):
                        try:
                            parsed_date = datetime.strptime(date_str, fmt).date()
                            break
                        except Exception:
                            continue
                    if not parsed_date:
                        try:
                            parsed_date = datetime.fromisoformat(date_str).date()
                        except Exception:
                            parsed_date = date.today()
                else:
                    parsed_date = date.today()

                transformed.append({
                    'merchant': txn.get('description', 'Unknown'),
                    'amount': float(txn.get('amount', 0) or 0),
                    'currency': txn.get('currency', 'PEN'),
                    'transaction_date': parsed_date,
                    'description': txn.get('description', 'Unknown'),
                    'category': txn.get('category')
                })

            logger.info(f"Vision fallback: transformed {len(transformed)} transactions")
            return transformed

        except Exception as e:
            logger.error(f"Vision fallback failed: {e}")
            return []

    def _make_direct_pdf_request(self, pdf_content: bytes, prompt: str, password: Optional[str] = None) -> List[Dict[str, Any]]:
        """Compatibility method for existing interfaces"""
        return self._extract_transactions_optimized(pdf_content, password)
