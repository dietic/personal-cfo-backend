import re
from datetime import datetime
from typing import List, Dict, Any
import json
import PyPDF2
import sys
import os

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text content from the PDF
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text_content = ""
            
            # Extract text from all pages
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            return text_content
            
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    except Exception as e:
        raise Exception(f"Error reading PDF file: {str(e)}")

def extract_transactions_from_statement(statement_text: str) -> List[Dict[str, Any]]:
    """
    Extract all transactions from a BCP VISA credit card statement.
    
    Args:
        statement_text (str): The raw text content of the bank statement
        
    Returns:
        List[Dict]: List of transaction dictionaries with keys:
                   - transaction_date, description, transaction_type, currency, amount
    """
    transactions = []
    
    # Split the text into lines for processing
    lines = statement_text.split('\n')
    
    # Pattern to match transaction lines
    # Format: Date Date Description [Location] OPERATION_TYPE Amount
    transaction_pattern = r'(\d{1,2}[A-Za-z]{3})\s+(\d{1,2}[A-Za-z]{3})\s+(.+?)\s+(CONSUMO|PAGO|CARGO)\s+([\d,]+\.?\d*-?)'
    
    # Month abbreviation mapping for Spanish months
    month_mapping = {
        'Ene': '01', 'Feb': '02', 'Mar': '03', 'Abr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08',
        'Set': '09', 'Oct': '10', 'Nov': '11', 'Dic': '12'
    }
    
    def parse_date(date_str: str, year: int = 2025) -> str:
        """Convert date string like '14Abr' to '2025-04-14'"""
        day = date_str[:len(date_str)-3]
        month_abbr = date_str[-3:]
        month = month_mapping.get(month_abbr, '01')
        return f"{year}-{month}-{day.zfill(2)}"
    
    def clean_description(desc: str) -> str:
        """Clean and standardize description"""
        # Remove extra spaces and clean up
        desc = re.sub(r'\s+', ' ', desc.strip())
        # Remove location codes like "PE", "FL", "CA", "WA", "MN" at the end
        desc = re.sub(r'\s+[A-Z]{2}$', '', desc)
        return desc
    
    def determine_currency_and_amount(amount_str: str, description: str) -> tuple:
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
        # US locations and services typically indicate USD
        usd_indicators = [
            'ORLANDO FL', 'MIAMI FL', 'KISSIMMEE FL', 'SAINT CLOUD FL',
            'Burbank CA', 'OPENAI', 'APPLE.COM', 'NETFLIX.COM', 'AMAZON',
            'STEAMGAMES.COM', 'Disney Plus', 'FRONTENDMASTERS.COM'
        ]
        
        # Check if description contains USD indicators
        if any(indicator in description.upper() for indicator in usd_indicators):
            return 'USD', amount
        else:
            return 'PEN', amount  # Peruvian Soles
    
    # Process each line
    current_year = 2025  # Based on the statement dates
    
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
            transaction_date = parse_date(consumption_date_str, current_year)
            
            # Clean description
            clean_desc = clean_description(description)
            
            # Determine currency and amount
            currency, amount = determine_currency_and_amount(amount_str, clean_desc)
            
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
    
    return transactions

def print_transactions(transactions: List[Dict[str, Any]]) -> None:
    """Print transactions in a formatted table"""
    print(f"{'Date':<12} {'Type':<10} {'Currency':<8} {'Amount':<12} {'Description'}")
    print("-" * 80)
    
    for tx in transactions:
        amount_str = f"{tx['amount']:,.2f}"
        print(f"{tx['transaction_date']:<12} {tx['transaction_type']:<10} {tx['currency']:<8} {amount_str:<12} {tx['description']}")

def save_to_json(transactions: List[Dict[str, Any]], filename: str = 'transactions.json') -> None:
    """Save transactions to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(transactions, f, indent=2, ensure_ascii=False)
    print(f"Transactions saved to {filename}")

def process_bank_statement_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Process a BCP VISA credit card statement PDF and extract all transactions.
    
    Args:
        pdf_path (str): Path to the PDF statement file
        
    Returns:
        List[Dict]: List of transaction dictionaries
    """
    # Extract text from PDF
    statement_text = extract_text_from_pdf(pdf_path)
    
    # Extract transactions from the text
    transactions = extract_transactions_from_statement(statement_text)
    
    return transactions

# Example usage with command line argument or file selection:
if __name__ == "__main__":
    # Check if PDF path is provided as command line argument
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]
    else:
        # Default PDF file name - you can change this or add file selection logic
        pdf_file_path = input("Enter the path to your BCP VISA statement PDF: ").strip()
        
        # Remove quotes if user added them
        pdf_file_path = pdf_file_path.strip('"\'')
    
    try:
        # Validate file exists and is a PDF
        if not os.path.exists(pdf_file_path):
            print(f"Error: File not found - {pdf_file_path}")
            sys.exit(1)
            
        if not pdf_file_path.lower().endswith('.pdf'):
            print(f"Error: File must be a PDF - {pdf_file_path}")
            sys.exit(1)
        
        # Process the PDF and extract transactions
        transactions = process_bank_statement_pdf(pdf_file_path)
        
        # Output clean JSON with all transactions
        print(json.dumps(transactions, indent=2, ensure_ascii=False))
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}", file=sys.stderr)
        sys.exit(1)