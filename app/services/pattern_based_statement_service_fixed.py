import re
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import PyPDF2
import io

from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class PatternBasedStatementService:
    """
    Service for extracting transactions using pattern matching instead of AI.
    Uses AI only for categorization.
    """
    
    def __init__(self):
        self.ai_service = AIService()
        
        # Month abbreviation mapping for Spanish months
        self.month_mapping = {
            'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
            'Set': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
        }
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text content from a PDF file."""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text_content = ""
            
            # Extract text from all pages
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            return text_content
            
        except Exception as e:
            raise Exception(f"Error reading PDF file: {str(e)}")

    def extract_transactions_from_statement(self, statement_text: str) -> List[Dict[str, Any]]:
        """
        Extract all transactions from a BCP VISA credit card statement using pattern matching.
        Fixed to correctly identify currency based on column position.
        """
        transactions = []
        
        # Split the text into lines for processing
        lines = statement_text.split('\n')
        
        def parse_date(date_str: str, year: int = 2025) -> str:
            """Convert date string like '14Abr' to '2025-04-14'"""
            day = date_str[:len(date_str)-3]
            month_abbr = date_str[-3:]
            month = self.month_mapping.get(month_abbr, '01')
            return f"{year}-{month}-{day.zfill(2)}"
        
        def clean_description(desc: str) -> str:
            """Clean and standardize description"""
            # Remove extra spaces and clean up
            desc = re.sub(r'\s+', ' ', desc.strip())
            return desc
        
        def determine_currency_and_amount(after_operation: str) -> tuple:
            """Determine currency based on spacing pattern after operation"""
            # Count leading spaces to determine which column the amount is in
            if re.match(r'^\s{15,}[\d,]+\.?\d*-?$', after_operation):
                # Many spaces (15+) = USD column (dollars)
                currency = 'USD'
                amount_str = after_operation.strip()
            elif re.match(r'^\s{5,14}[\d,]+\.?\d*-?$', after_operation):
                # Fewer spaces (5-14) = PEN column (soles)
                currency = 'PEN'
                amount_str = after_operation.strip()
            else:
                # Fallback - if pattern doesn't match, assume PEN
                currency = 'PEN'
                amount_str = after_operation.strip()
            
            # Process amount
            is_negative = amount_str.endswith('-')
            clean_amount = amount_str.replace('-', '').replace(',', '')
            
            if clean_amount:
                amount = float(clean_amount)
                if is_negative:
                    amount = -amount
            else:
                amount = 0.0
                
            return currency, amount
        
        # Process each line
        current_year = 2025  # Based on the statement dates
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match transaction pattern: capture everything before operation and everything after
            operation_match = re.search(r'(.+?)\s+(CONSUMO|PAGO|CARGO)(.*)$', line)
            
            if operation_match:
                before_operation = operation_match.group(1)
                operation_type = operation_match.group(2)
                after_operation = operation_match.group(3)
                
                # Extract dates and description from before_operation
                date_match = re.match(r'(\d{1,2}[A-Za-z]{3})\s+(\d{1,2}[A-Za-z]{3})\s+(.+)', before_operation)
                
                if date_match:
                    process_date_str = date_match.group(1)
                    consumption_date_str = date_match.group(2)
                    description = date_match.group(3)
                    
                    # Parse dates
                    transaction_date = parse_date(consumption_date_str, current_year)
                    
                    # Clean description
                    clean_desc = clean_description(description)
                    
                    # Determine currency and amount based on spacing pattern
                    currency, amount = determine_currency_and_amount(after_operation)
                    
                    # Map operation types
                    type_mapping = {
                        'CONSUMO': 'Purchase',
                        'PAGO': 'Payment',
                        'CARGO': 'Charge'
                    }
                    
                    transaction = {
                        'transaction_date': transaction_date,
                        'description': clean_desc,
                        'transaction_type': type_mapping.get(operation_type, operation_type),
                        'currency': currency,
                        'amount': amount
                    }
                    
                    transactions.append(transaction)
        
        # Sort transactions by date
        transactions.sort(key=lambda x: x['transaction_date'])
        
        logger.info(f"Extracted {len(transactions)} transactions using pattern matching")
        return transactions
    
    async def categorize_transactions_with_ai(
        self, 
        transactions: List[Dict[str, Any]], 
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """Use AI to categorize transactions with user's categories"""
        try:
            # Prepare transactions for AI categorization
            transaction_summaries = []
            for txn in transactions:
                summary = f"Date: {txn['transaction_date']}, Description: {txn['description']}, Amount: {txn['currency']} {txn['amount']}"
                transaction_summaries.append(summary)
            
            # Create categorization prompt
            categories_list = ", ".join(f'"{cat}"' for cat in categories)
            prompt = f"""
            Categorize these credit card transactions using ONLY the provided categories.
            
            Available categories: [{categories_list}]
            
            Transactions to categorize:
            {chr(10).join(f"{i+1}. {summary}" for i, summary in enumerate(transaction_summaries))}
            
            Return a JSON array with one category per transaction:
            ["category1", "category2", "category3", ...]
            
            Rules:
            - Use ONLY categories from the provided list
            - If uncertain, use "Misc"
            - Return exactly {len(transactions)} categories in the same order
            """
            
            response = self.ai_service.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a transaction categorization expert. Always respond with valid JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            category_assignments = json.loads(content)
            
            # Validate we have the right number of categories
            if len(category_assignments) != len(transactions):
                logger.warning(f"AI returned {len(category_assignments)} categories for {len(transactions)} transactions. Using fallback.")
                category_assignments = ["Misc"] * len(transactions)
            
            # Apply categories to transactions
            categorized_transactions = []
            for i, txn in enumerate(transactions):
                category = category_assignments[i] if i < len(category_assignments) else "Misc"
                
                # Validate category is in allowed list
                if category not in categories:
                    category = "Misc"
                
                categorized_txn = txn.copy()
                categorized_txn['category'] = category
                categorized_transactions.append(categorized_txn)
            
            logger.info(f"Successfully categorized {len(categorized_transactions)} transactions with AI")
            return categorized_transactions
            
        except Exception as e:
            logger.error(f"AI categorization failed: {str(e)}")
            # Fallback: assign "Misc" to all transactions
            categorized_transactions = []
            for txn in transactions:
                categorized_txn = txn.copy()
                categorized_txn['category'] = "Misc"
                categorized_transactions.append(categorized_txn)
            return categorized_transactions

    async def process_statement_complete(
        self, 
        file_content: bytes, 
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Complete processing: extract transactions with patterns + categorize with AI
        """
        try:
            # Step 1: Extract text from PDF
            statement_text = self.extract_text_from_pdf(file_content)
            
            # Step 2: Extract transactions using pattern matching
            transactions = self.extract_transactions_from_statement(statement_text)
            
            if not transactions:
                logger.warning("No transactions found using pattern matching")
                return []
            
            # Step 3: Categorize transactions using AI
            categorized_transactions = await self.categorize_transactions_with_ai(
                transactions, categories
            )
            
            logger.info(f"Successfully processed statement: {len(categorized_transactions)} transactions")
            return categorized_transactions
            
        except Exception as e:
            logger.error(f"Error processing statement: {str(e)}")
            raise Exception(f"Failed to process statement: {str(e)}")
