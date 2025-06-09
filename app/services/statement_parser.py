import pandas as pd
import PyPDF2
from typing import List, Dict, Any, Tuple, Optional
import re
from datetime import datetime
import io
import json
import openai
from app.core.config import settings

class StatementParser:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def detect_currency(self, text: str, amount_str: str) -> str:
        """Detect currency from text and amount string"""
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

    def parse_pdf_statement(self, file_content: bytes) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Parse PDF bank statement using ChatGPT for intelligent extraction"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            # Use ChatGPT to extract transactions and statement period
            transactions, statement_period = self._extract_transactions_with_ai(text)
            return transactions, statement_period
            
        except Exception as e:
            raise ValueError(f"Error parsing PDF: {str(e)}")

    def _extract_transactions_with_ai(self, text: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Use ChatGPT to intelligently extract transactions and statement period from PDF text"""
        prompt = f"""
        You are an expert at analyzing bank statements. Extract all transactions and the statement period from this bank statement text.

        Bank Statement Text:
        {text}

        Please extract:
        1. All transactions with their details
        2. The statement period (start and end dates)

        Return a JSON object with this exact structure:
        {{
            "statement_period": {{
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "month": "YYYY-MM"
            }},
            "transactions": [
                {{
                    "date": "YYYY-MM-DD",
                    "merchant": "merchant name",
                    "description": "transaction description",
                    "amount": 123.45,
                    "currency": "USD or PEN",
                    "type": "debit or credit"
                }}
            ]
        }}

        Important guidelines:
        - Extract ALL transactions, not just a sample
        - Amounts should be positive numbers
        - Currency should be "USD" if dollar symbol ($) is found, "PEN" if Sol symbol (S/.) is found
        - Date format must be YYYY-MM-DD
        - Be very careful with date parsing - look for context clues about date format
        - For merchant names, clean up and normalize the text
        - Include both debit and credit transactions
        - If statement period is not explicitly stated, infer from transaction dates
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert financial document parser. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
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
                            
                            transactions.append({
                                'merchant': str(tx.get("merchant", "")).strip(),
                                'amount': float(tx.get("amount", 0)),
                                'currency': tx.get("currency", "USD"),
                                'transaction_date': transaction_date,
                                'description': str(tx.get("description", tx.get("merchant", ""))).strip(),
                                'type': tx.get("type", "debit")
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

    def _extract_transactions_from_text_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Fallback method for basic transaction extraction if AI fails"""
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

    def _parse_date(self, date_str: str) -> str:
        """Parse date string to ISO format"""
        # Try different date formats
        formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y']
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # If no format works, return today's date as fallback
        return datetime.now().strftime('%Y-%m-%d')

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
