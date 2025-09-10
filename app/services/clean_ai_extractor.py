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
            # Store user_id temporarily for the private method
            self._current_user_id = user_id
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

            # Get user_id from method parameters (extract_transactions passes user_id)
            # We need to access the user_id from the extract_transactions method
            # Since this is a private method called by extract_transactions, we'll need to modify the signature
            # For now, let's assume user_id is available in the instance or we need to modify the method signature
            
            # For this fix, let me check if we can access user_id from the instance
            # If not, we'll need to modify the method signature to accept user_id
            
            # Let me check how extract_transactions calls this method
            user_id = getattr(self, '_current_user_id', None)
            merchant_info = ""
            
            if user_id:
                try:
                    from app.services.merchant_service import MerchantService
                    merchant_info = MerchantService.get_merchants_for_ai_prompt(self.db_session, user_id)
                except Exception as e:
                    logger.warning(f"Failed to get merchant info: {str(e)}")

            # Create universal prompt for any bank statement with merchant standardization
            prompt = f"""Extract ALL purchase transactions from this bank statement.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY actual purchases/transactions (merchant charges, purchases, payments)
2. EXCLUDE: fees, balance transfers, payments between accounts, adjustments, interests
3. Determine the statement period from the FIRST PAGE header (e.g., "Statement period", "Periodo", "Del ... al ..."). Use this to infer the CORRECT YEAR for each transaction date when the statement lists dates without a year.
4. For each transaction return these fields:
   - date: full ISO date in format YYYY-MM-DD (include the correct year inferred from the statement period; if the period spans months/years, use the appropriate year for each date)
   - merchant: standardized merchant name (see merchant standardization rules below)
   - description: complete original merchant/transaction description as printed (preserve names, remove internal codes)
   - amount: numeric amount (positive number, use dot as decimal separator)
   - currency: currency code (PEN, USD, EUR, etc.)
5. Handle multiple currencies if present.
6. Return ONLY the JSON array with no additional text.

MERCHANT STANDARDIZATION RULES:
{merchant_info if merchant_info else "No existing merchants found. Standardize new merchant names using common brand names."}

When standardizing merchant names:
- Normalize the raw description before matching: trim, collapse spaces, remove diacritics, and strip store/location noise (districts, “PE/PERU”, “LIMA”, “SUC/STORE #”, “TIENDA”, “S.A.”, “SAC”, “E.I.R.L.”, “E-COM”, “ECOM”, “POS”, “APP”, “WEB”, “QR”, card scheme codes).
- Use brand inference, not exact lists. Prefer widely known consumer brands based on general knowledge of companies operating globally and in Latin America (food delivery, supermarkets, electronics, apparel, streaming, marketplaces, app stores, ride-hailing).
- Fuzzy/substring match common brand tokens and variants (ignore case/punctuation): e.g., “RAPPI”, “RAPPI*RESTAURANTES”, “RAPPI PRIME” → “Rappi”; “UBER TRIP/UBER*EATS” → “Uber” or “Uber Eats”; “GOOGLE*”/“Google Play” → “Google Play”; “APPLE.COM/BILL/ITUNES” → “Apple”; “AMAZON*”/“AMZN” → “Amazon”; “MERCADOPAGO/MERCADO PAGO” → infer underlying merchant if present, else “Mercado Pago”.
- If the string contains a domain or host, map it to the brand: take the registrable domain (before the TLD) and title-case it (e.g., “STEAMGAMES.COM”, “OPENAI.COM”, “SPOTIFY.COM”, “SHEIN.COM”, “ALiexpress.com”, “NETFLIX.COM” → “Steam”, “OpenAI”, “Spotify”, “Shein”, “Netflix”).
- For payments via gateways/aggregators (e.g., “NIUBIZ”, “IZIPAY”, “CULQI”, “STRIPE”, “PAYU”, “DLOCAL”, “MERCADO PAGO”):
  1) Look left/right for a recognizable merchant token in the same line; if found, use that merchant.
  2) If none is present, return the aggregator name itself (e.g., “Niubiz”) only as a fallback.
- **Collapse “brand + descriptor” to the brand only:** If a recognized brand token appears and is immediately followed by a generic descriptor, drop everything after the brand. Examples:
  - “APPARKA CLINICA”, “APPARKA GUARDIA CIVIL”, “APPARKA SEDE XYZ” → “Apparka”
  - “RAPPI RESTAURANTES”, “COOLBOX TIENDA 123”, “SMARTFIT LOS OLIVOS” → “Rappi”, “Coolbox”, “Smartfit”
  - This rule applies unless the suffix forms a distinct, widely known sub-brand (keep “Uber Eats”, “Google Play”).
- Descriptor stop-list (strip when following a brand token; ignore accents/case): clinica, restaurante(s), farmacia(s), guardia civil, comisaria, sede, sucursal, agencia, tienda, local, sede central, oficina, mall, centro comercial, larcomar, miraflores, san isidro, san borja, surco, los olivos, independencia, callao, arequipa, trujillo, chiclayo, cusco, piura, loja, lima, peru, pe, s.a., sac, eirl, sa, suc, store, store numbers.
- Handle local brand noise and branches: remove neighborhood/district names and store numbers; keep just the brand (e.g., “COOLBOX MIRAFLORES” → “Coolbox”; “SAGA FALABELLA LARCOMAR” → “Saga Falabella”).
- Prefer the more specific sub-brand when unambiguous (e.g., “Uber Eats” over “Uber” if “EATS” appears; “Google Play” over “Google” if “GOOGLE*” + app/billing pattern).
- Use proper capitalization (e.g., “Makro” not “MAKRO”).
- Only return “Unknown” when no recognizable brand token, domain, or aggregator-adjacent merchant can be inferred with high confidence — do not return “Unknown” for well-known brands.

EXPECTED OUTPUT FORMAT - JSON array:
[
  {{
    "date": "2025-05-12",
    "merchant": "Makro",
    "description": "MAKRO INDEPENDENCIA LIMA PE",
    "amount": 195.50,
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
                    'merchant': txn.get('merchant', 'Unknown'),  # Use AI-extracted merchant
                    'amount': float(txn.get('amount', 0)),
                    'currency': txn.get('currency', 'PEN'),
                    'transaction_date': parsed_date,  # parsed date object
                    'description': txn.get('description', txn.get('merchant', 'Unknown')),  # fallback to merchant if no description
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
                "merchant (standardized name), description (original text), amount (number, dot decimal), currency (code). Exclude fees/interests/transfers.\n\n"
                "MERCHANT STANDARDIZATION RULES:\n"
                "- Remove location details, store numbers, and unnecessary text like \"Clinica\", \"Restaurantes\", \"Guardia Civil\"\n"
                "- Use proper capitalization (e.g., \"Makro\" not \"MAKRO\")\n"
                "- Common brand mappings (including Peruvian brands): Makro, Metro, Wong, Ripley, Falabella, Tottus, Plaza Vea, Vivanda, Coolbox, Smartfit, Saga Falabella, Oeschle, Paris, Hiraoka, La Curacao\n"
                "- Specific examples:\n"
                "  - \"Apparka Clinica\" → \"Apparka\"\n"
                "  - \"Pedidosya Restaurantes\" → \"Pedidosya\"\n"  
                "  - \"Apparka Guardia Civil\" → \"Apparka\"\n"
                "  - \"COOLBOX MIRAFLORES\" → \"Coolbox\"\n"
                "  - \"SMARTFIT LOS OLIVOS\" → \"Smartfit\"\n"
                "- For well-known brands, even if not in the examples above, try to recognize and standardize them\n"
                "- Only return \"Unknown\" for truly unrecognizable merchant names, not for well-known brands"
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
                    'merchant': txn.get('merchant', 'Unknown'),  # Use AI-extracted merchant
                    'amount': float(txn.get('amount', 0) or 0),
                    'currency': txn.get('currency', 'PEN'),
                    'transaction_date': parsed_date,
                    'description': txn.get('description', txn.get('merchant', 'Unknown')),  # fallback to merchant if no description
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
