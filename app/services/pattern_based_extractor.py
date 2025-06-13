"""
Pattern-based transaction extractor for BCP VISA credit card statements.
Uses regex patterns to extract transactions and only uses AI for categorization.
"""

import re
import PyPDF2
import io
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PatternBasedExtractor:
    """Extract transactions using pattern matching instead of AI"""
    
    def __init__(self):
        # Month abbreviation mapping for Spanish months
        self.month_mapping = {
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
            'Set': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        }
        
        # USD indicators for currency detection
        self.usd_indicators = [
            'ORLANDO FL', 'MIAMI FL', 'KISSIMMEE FL', 'SAINT CLOUD FL',
            'Burbank CA', 'OPENAI', 'APPLE.COM', 'NETFLIX.COM', 'AMAZON',
            'STEAMGAMES.COM', 'Disney Plus', 'FRONTENDMASTERS.COM'
        ]
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text content from PDF file content"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text_content = ""
            
            # Extract text from all pages
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            return text_content
            
        except Exception as e:
            raise ValueError(f"Error reading PDF file: {str(e)}")
    
    def parse_date(self, date_str: str, year: int = 2024) -> date:
        """Convert date string like '14Abr' to date object"""
        try:
            day = date_str[:len(date_str)-3]
            month_abbr = date_str[-3:]
            month = self.month_mapping.get(month_abbr, '01')
            return datetime.strptime(f"{year}-{month}-{day.zfill(2)}", "%Y-%m-%d").date()
        except Exception as e:
            logger.warning(f"Error parsing date {date_str}: {e}")
            return datetime.now().date()
    
    def clean_description(self, desc: str) -> str:
        """Clean and standardize description"""
        # Remove extra spaces and clean up
        desc = re.sub(r'\s+', ' ', desc.strip())
        # Remove location codes like "PE", "FL", "CA", "WA", "MN" at the end
        desc = re.sub(r'\s+[A-Z]{2}$', '', desc)
        return desc
    
    def determine_currency_and_amount(self, amount_str: str, description: str) -> tuple:
        """Determine currency and clean amount based on context"""
        # Remove any negative sign for processing
        is_negative = amount_str.endswith('-')
        clean_amount = amount_str.replace('-', '').replace(',', '')
        
        # Convert to float
        amount = float(clean_amount)
        
        # If it's a payment (negative), keep it negative
        if is_negative:
            amount = -amount
        
        # Determine currency based on description and amount patterns
        # Check if description contains USD indicators
        if any(indicator in description.upper() for indicator in self.usd_indicators):
            return 'USD', amount
        else:
            return 'PEN', amount  # Peruvian Soles
    
    def extract_transactions_from_statement(self, statement_text: str) -> List[Dict[str, Any]]:
        """Extract all transactions from a BCP VISA credit card statement"""
        transactions = []
        
        # Split the text into lines for processing
        lines = statement_text.split('\n')
        
        # Pattern to match transaction lines
        # Format: Date Date Description [Location] OPERATION_TYPE Amount
        transaction_pattern = r'(\d{1,2}[A-Za-z]{3})\s+(\d{1,2}[A-Za-z]{3})\s+(.+?)\s+(CONSUMO|PAGO|CARGO)\s+([\d,]+\.?\d*-?)'
        
        # Process each line
        current_year = 2024  # Based on the statement dates
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match transaction pattern
            match = re.search(transaction_pattern, line)
            if match:
                process_date_str = match.group(1)
                consumption_date_str = match.group(2)
                description = match.group(3)
                operation_type = match.group(4)
                amount_str = match.group(5)
                
                # Parse dates
                transaction_date = self.parse_date(consumption_date_str, current_year)
                
                # Clean description
                clean_desc = self.clean_description(description)
                
                # Determine currency and amount
                currency, amount = self.determine_currency_and_amount(amount_str, clean_desc)
                
                # Map operation types
                type_mapping = {
                    'CONSUMO': 'Purchase',
                    'PAGO': 'Payment',
                    'CARGO': 'Charge'
                }
                
                transaction = {
                    'transaction_date': transaction_date,
                    'merchant': clean_desc,  # Map to merchant field for backend compatibility
                    'description': clean_desc,
                    'amount': abs(amount),  # Store as positive, use transaction_type for direction
                    'currency': currency,
                    'type': operation_type,
                    'transaction_type': type_mapping.get(operation_type, operation_type)
                }
                
                transactions.append(transaction)
        
        # Sort transactions by date
        transactions.sort(key=lambda x: x['transaction_date'])
        
        logger.info(f"Extracted {len(transactions)} transactions using pattern matching")
        return transactions
    
    def extract_transactions_from_pdf(
        self, 
        file_content: bytes, 
        allowed_categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Main extraction method that takes PDF content and returns extracted transactions
        
        Args:
            file_content: PDF file content as bytes
            allowed_categories: List of categories (not used in extraction, only for AI categorization)
            
        Returns:
            List of transaction dictionaries
        """
        try:
            # Extract text from PDF
            statement_text = self.extract_text_from_pdf(file_content)
            
            # Extract transactions using pattern matching
            transactions = self.extract_transactions_from_statement(statement_text)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error extracting transactions from PDF: {str(e)}")
            raise ValueError(f"Failed to extract transactions: {str(e)}")
