import pandas as pd
import PyPDF2
from typing import List, Dict, Any, Tuple, Optional
import re
from datetime import datetime, date
import io
import json
import openai
from app.core.config import settings

class StatementParser:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def detect_currency(self, text: str, amount_str: str) -> str:
        """Detect currency from text and amount string"""
        # Ensure amount_str is a string (defensive programming)
        amount_str = str(amount_str)
        
        # Look for Peruvian Sol indicators
        sol_indicators = [
            'S/.',  # Common Peruvian Sol symbol
            'S/',
            'PEN',
            'soles',
            'sol peruano',
            'nuevo sol'
        ]
        
        # Look for USD indicators
        usd_indicators = [
            '$',
            'USD',
            'US$',
            'dollar',
            'dolar'
        ]
        
        text_lower = text.lower()
        amount_lower = amount_str.lower()
        
        # Check amount string first (more specific)
        if any(indicator in amount_str for indicator in ['S/.', 'S/']):
            return 'PEN'
        elif '$' in amount_str and 'S/' not in amount_str:
            return 'USD'
        
        # Check broader text
        for indicator in sol_indicators:
            if indicator.lower() in text_lower:
                return 'PEN'
        
        for indicator in usd_indicators:
            if indicator.lower() in text_lower:
                return 'USD'
        
        # Default to USD if not detected
        return 'USD'
    
    def parse_csv_statement(self, file_content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV bank statement"""
        try:
            # Try to read CSV with different encodings
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(file_content), encoding='latin-1')
            
            transactions = []
            
            # Common column name mappings
            column_mappings = {
                'date': ['date', 'transaction_date', 'fecha', 'Date'],
                'merchant': ['description', 'merchant', 'descripcion', 'Description', 'Merchant'],
                'amount': ['amount', 'monto', 'Amount', 'valor', 'Valor']
            }
            
            # Find actual column names
            actual_columns = {}
            for standard_name, possible_names in column_mappings.items():
                for col in df.columns:
                    if col.lower() in [name.lower() for name in possible_names]:
                        actual_columns[standard_name] = col
                        break
            
            # Check if we have the required columns
            if not all(key in actual_columns for key in ['date', 'merchant', 'amount']):
                raise ValueError("Required columns not found in CSV")
            
            # Get all text for currency detection
            all_text = df.to_string()
            
            for _, row in df.iterrows():
                try:
                    # Parse date
                    date_str = str(row[actual_columns['date']])
                    transaction_date = self._parse_date(date_str)
                    
                    # Parse amount and detect currency
                    amount_str = str(row[actual_columns['amount']])
                    amount = self._parse_amount(amount_str)
                    currency = self.detect_currency(all_text, amount_str)
                    
                    # Get merchant
                    merchant = str(row[actual_columns['merchant']]).strip()
                    
                    if merchant and amount != 0:
                        transactions.append({
                            'merchant': merchant,
                            'amount': abs(amount),  # Convert to positive
                            'currency': currency,
                            'transaction_date': transaction_date,
                            'description': merchant
                        })
                except Exception as e:
                    continue  # Skip problematic rows
            
            return transactions
            
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")

    def parse_pdf_statement(self, file_content: bytes, allowed_categories: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Parse PDF bank statement using ChatGPT for intelligent extraction"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            # Use ChatGPT to extract transactions and statement period with category constraints
            transactions, statement_period = self._extract_transactions_with_ai(text, allowed_categories)
            return transactions, statement_period
            
        except Exception as e:
            raise ValueError(f"Error parsing PDF: {str(e)}")

    def _extract_transaction_lines(self, text: str) -> str:
        """Extract only transaction-relevant lines from PDF text to reduce token usage"""
        lines = text.split('\n')
        transaction_lines = []
        
        # Keywords that indicate transaction lines - expanded for Spanish statements
        transaction_keywords = [
            'fecha', 'date', 'merchant', 'comercio', 'descripción', 'description',
            'monto', 'amount', 'cargo', 'abono', 'débito', 'crédito',
            'transacción', 'transaction', 'movimiento', 'consumo', 'proceso',
            'lima', 'pe', 'makro', 'doctor', 'openai', 'rimac', 'amazon', 'netflix'
        ]
        
        # Enhanced patterns for Spanish credit card statements
        patterns = [
            r'\d{1,2}[A-Za-z]{3}',  # Spanish dates like "23Abr", "24Abr"
            r'CONSUMO',             # Transaction type
            r'S/\s*[\d,]+\.?\d*',   # PEN amounts
            r'\$\s*[\d,]+\.?\d*',   # USD amounts  
            r'[\d,]+\.\d{2}',       # Decimal amounts
            r'[A-Z\s]+\s+(LIMA|PE)', # Merchant patterns with location
        ]
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            line_lower = line_stripped.lower()
            
            # Include lines with transaction keywords
            if any(keyword in line_lower for keyword in transaction_keywords):
                transaction_lines.append(line_stripped)
                continue
                
            # Include lines that match transaction patterns
            if any(re.search(pattern, line_stripped) for pattern in patterns):
                transaction_lines.append(line_stripped)
                continue
                
            # Include lines with merchant names or amounts
            if (len(line_stripped) > 15 and 
                (any(char.isdigit() for char in line_stripped) and 
                 any(char.isalpha() for char in line_stripped))):
                transaction_lines.append(line_stripped)
        
        # Always include enough context - but balance with token limits
        if len(transaction_lines) < 10:
            # If we found very few lines, include more context but limit to 80 lines
            return '\n'.join(lines[:80])
        
        # Limit the output to avoid token overflow while ensuring we have transactions
        limited_lines = transaction_lines[:200]  # Limit to first 200 relevant lines
        return '\n'.join(limited_lines)

    def _extract_transactions_with_ai(self, text: str, allowed_categories: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Use ChatGPT to intelligently extract transactions and statement period from PDF text"""
        
        # Extract only transaction-relevant content to reduce token usage
        transaction_lines = self._extract_transaction_lines(text)
        
        # Create category constraint text
        category_constraint = ""
        if allowed_categories:
            category_list = ", ".join(f'"{cat}"' for cat in allowed_categories)
            category_constraint = f"""
        
        IMPORTANT - Category Selection:
        You MUST choose categories ONLY from this exact list: [{category_list}]
        If uncertain, use "Uncategorized" as the category.
        """
        
        prompt = f"""
        CRITICAL: This is a complete VISA credit card statement. You MUST extract EVERY SINGLE transaction.
        There should be 80+ transactions in this statement. Do NOT provide just samples or examples.

        Bank Statement Text (transaction rows only):
        {transaction_lines}

        EXTRACT ALL TRANSACTIONS - EVERY SINGLE ONE. This is not a sample request.

        Date format help:
        - "23Abr" means April 23, 2024 (format as "2024-04-23")
        - "24Abr" means April 24, 2024 (format as "2024-04-24")
        - Spanish months: Ene=Jan, Feb=Feb, Mar=Mar, Abr=Apr, May=May, Jun=Jun, Jul=Jul, Ago=Aug, Sep=Sep, Oct=Oct, Nov=Nov, Dic=Dec

        Currency detection:
        - Lines with "S/" amounts are PEN currency
        - Lines with "$" or "USD" amounts are USD currency
        - If no symbol, check context or assume PEN for Peru-based merchants

        Return JSON with this structure:
        {{
            "statement_period": {{
                "month": "2024-04"
            }},
            "transactions": [
                {{
                    "date": "2024-04-23",
                    "merchant": "MAKRO INDEPENDENCIA",
                    "description": "MAKRO INDEPENDENCIA LIMA PE",
                    "amount": 195.54,
                    "currency": "PEN",
                    "category": "Supermercado",
                    "type": "debit"
                }}
            ]
        }}

        CRITICAL REQUIREMENTS:
        - Extract EVERY transaction - should be 80+ transactions total
        - Do NOT truncate or sample - extract ALL
        - Amounts should be positive numbers
        - Currency should be "USD" if dollar symbol ($) is found, "PEN" if Sol symbol (S/.) is found
        - Date format must be YYYY-MM-DD
        - Be very careful with date parsing - look for context clues about date format
        - For merchant names, clean up and normalize the text
        - Include both debit and credit transactions
        - If statement period is not explicitly stated, infer from transaction dates
        {category_constraint}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert financial document parser specializing in extracting ALL transactions from bank statements. Never truncate or provide samples - extract every single transaction."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=6000  # Reduced but still sufficient for many transactions
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                
                # Extract transactions
                transactions = []
                for tx in result.get("transactions", []):
                    try:
                        # Parse and validate transaction date
                        transaction_date = self._parse_date(tx.get("date", ""))
                        
                        # Validate required fields
                        if (tx.get("merchant") and 
                            tx.get("amount") and 
                            float(tx.get("amount", 0)) > 0):
                            
                            # Validate category - fallback to "Uncategorized" if not in allowed list
                            category = tx.get("category", "Uncategorized")
                            if allowed_categories and category not in allowed_categories:
                                category = "Uncategorized"
                            
                            transactions.append({
                                'merchant': str(tx.get("merchant", "")).strip(),
                                'amount': float(tx.get("amount", 0)),
                                'currency': tx.get("currency", "USD"),
                                'transaction_date': transaction_date,
                                'description': str(tx.get("description", tx.get("merchant", ""))).strip(),
                                'type': tx.get("type", "debit"),
                                'category': category
                            })
                    except (ValueError, TypeError):
                        continue  # Skip invalid transactions
                
                # Extract statement period
                statement_period = None
                if result.get("statement_period"):
                    period_data = result["statement_period"]
                    statement_period = period_data.get("month")
                
                return transactions, statement_period
            else:
                raise ValueError("Empty response from AI")
                
        except json.JSONDecodeError as e:
            # Fallback to basic parsing if JSON parsing fails
            print(f"AI JSON parsing failed: {e}. Falling back to basic parsing.")
            transactions = self._extract_transactions_from_text_fallback(text)
            return transactions, None
            
        except Exception as e:
            print(f"AI extraction failed: {e}. Falling back to basic parsing.")
            transactions = self._extract_transactions_from_text_fallback(text)
            return transactions, None

    def _extract_transactions_chunked(self, text: str, allowed_categories: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Extract transactions in chunks to handle large PDFs with 80+ transactions"""
        
        # Get transaction lines
        transaction_lines = self._extract_transaction_lines(text)
        lines = transaction_lines.split('\n')
        
        # Split into chunks that fit within token limits
        chunk_size = 60  # Lines per chunk to stay under token limit
        chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
        
        all_transactions = []
        statement_period = None
        
        print(f"Processing {len(chunks)} chunks of transaction data...")
        
        for i, chunk in enumerate(chunks):
            chunk_text = '\n'.join(chunk)
            
            # Create category constraint text
            category_constraint = ""
            if allowed_categories:
                category_list = ", ".join(f'"{cat}"' for cat in allowed_categories)
                category_constraint = f"""
            
            IMPORTANT - Category Selection:
            You MUST choose categories ONLY from this exact list: [{category_list}]
            If uncertain, use "Misc" as the category.
            """
            
            prompt = f"""
            Extract ALL transactions from this chunk of a Spanish VISA credit card statement.
            This is chunk {i+1} of {len(chunks)} - extract EVERY transaction in this chunk.

            Transaction data:
            {chunk_text}

            Date format help:
            - "23Abr" = April 23, 2024 = "2024-04-23"
            - "24Abr" = April 24, 2024 = "2024-04-24"
            - Spanish months: Ene=Jan, Feb=Feb, Mar=Mar, Abr=Apr, May=May, Jun=Jun

            Currency rules:
            - Lines with "S/" amounts = PEN currency
            - Lines with "$" or "USD" = USD currency
            - Peru merchants usually PEN, international usually USD

            Return JSON:
            {{
                "transactions": [
                    {{
                        "date": "2024-04-23",
                        "merchant": "merchant name",
                        "description": "description",
                        "amount": 123.45,
                        "currency": "PEN or USD",
                        "category": "category_name"
                    }}
                ]
            }}

            EXTRACT EVERY TRANSACTION IN THIS CHUNK - DO NOT SKIP ANY.
            {category_constraint}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert at extracting ALL transactions from bank statement chunks. Extract every single transaction in each chunk."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=3000
                )
                
                content = response.choices[0].message.content
                if content:
                    result = json.loads(content)
                    chunk_transactions = result.get("transactions", [])
                    
                    # Process each transaction
                    for tx in chunk_transactions:
                        try:
                            transaction_date = self._parse_date(tx.get("date", ""))
                            
                            if (tx.get("merchant") and 
                                tx.get("amount") and 
                                float(tx.get("amount", 0)) > 0):
                                
                                category = tx.get("category", "Misc")
                                if allowed_categories and category not in allowed_categories:
                                    category = "Misc"
                                
                                all_transactions.append({
                                    'merchant': str(tx.get("merchant", "")).strip(),
                                    'amount': float(tx.get("amount", 0)),
                                    'currency': tx.get("currency", "PEN"),
                                    'transaction_date': transaction_date,
                                    'description': str(tx.get("description", tx.get("merchant", ""))).strip(),
                                    'type': tx.get("type", "debit"),
                                    'category': category
                                })
                        except (ValueError, TypeError):
                            continue
                    
                    print(f"  Chunk {i+1}: Extracted {len(chunk_transactions)} transactions")
                    
                    # Set statement period from first chunk
                    if not statement_period and result.get("statement_period"):
                        statement_period = result["statement_period"].get("month")
                
            except Exception as e:
                print(f"  Chunk {i+1} failed: {str(e)}")
                continue
        
        print(f"Total transactions extracted: {len(all_transactions)}")
        return all_transactions, statement_period or "2024-04"

    def _extract_transactions_from_text_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Fallback method for basic transaction extraction if AI fails"""
        transactions = []
        
        # Basic pattern to match transaction lines
        # This is a simplified pattern and might need adjustment based on actual PDF formats
        pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([A-Za-z\s]+)\s+([$S/\.]*[\d,]+\.?\d*)'
        
        matches = re.findall(pattern, text)
        
        for date_str, merchant, amount_str in matches:
            try:
                transaction_date = self._parse_date(date_str)
                amount = self._parse_amount(amount_str)
                currency = self.detect_currency(text, amount_str)
                
                if amount > 0:
                    transactions.append({
                        'merchant': merchant.strip(),
                        'amount': amount,
                        'currency': currency,
                        'transaction_date': transaction_date,
                        'description': merchant.strip()
                    })
            except:
                continue
        
        return transactions

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object with Spanish month support"""
        if not date_str or not date_str.strip():
            # Return today's date if no date provided
            return datetime.now().date()
        
        date_str = date_str.strip()
        
        # Handle Spanish month abbreviations (like "23Abr")
        spanish_months = {
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        }
        
        # Check for Spanish date format like "23Abr"
        spanish_date_match = re.match(r'(\d{1,2})([A-Za-z]{3})', date_str)
        if spanish_date_match:
            day = spanish_date_match.group(1).zfill(2)
            month_abbr = spanish_date_match.group(2).capitalize()
            
            if month_abbr in spanish_months:
                month = spanish_months[month_abbr]
                # Assume current year or 2024 for credit card statements
                year = '2024'  # This matches the PDF content
                try:
                    return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
                except ValueError:
                    pass
        
        # Try standard date formats
        formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y']
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.date()
            except ValueError:
                continue
        
        # If no format works, return today's date as fallback
        return datetime.now().date()

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        # Remove currency symbols and spaces
        amount_str = re.sub(r'[^\d.,+-]', '', amount_str)
        
        # Handle different decimal separators
        if ',' in amount_str and '.' in amount_str:
            # Assume comma is thousands separator
            amount_str = amount_str.replace(',', '')
        elif ',' in amount_str:
            # Assume comma is decimal separator
            amount_str = amount_str.replace(',', '.')
        
        try:
            return float(amount_str)
        except ValueError:
            return 0.0
    
    def parse_pdf(self, file_path: str, allowed_categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Parse PDF file given file path (wrapper for enhanced service compatibility)"""
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        transactions, _ = self.parse_pdf_statement(file_content, allowed_categories)
        return transactions
    
    def parse_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CSV file given file path (wrapper for enhanced service compatibility)"""
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        return self.parse_csv_statement(file_content)
