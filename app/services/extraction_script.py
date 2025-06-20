import re
from datetime import datetime
from typing import List, Dict, Any
import json
import sys
import os

# Use pdfplumber instead of PyPDF2 for better PDF handling
try:
    import pdfplumber
    PDF_LIBRARY = 'pdfplumber'
except ImportError:
    try:
        import PyPDF2
        PDF_LIBRARY = 'PyPDF2'
    except ImportError:
        raise ImportError("Please install either pdfplumber or PyPDF2: pip install pdfplumber")

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text content from a PDF file using the best available library.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text content from the PDF
    """
    try:
        if PDF_LIBRARY == 'pdfplumber':
            # Use pdfplumber for better handling of complex PDFs
            with pdfplumber.open(pdf_path) as pdf:
                text_content = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
                return text_content
        else:
            # Fallback to PyPDF2
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

def extract_transactions_from_statement(statement_text: str, bank_type: str = "BCP") -> List[Dict[str, Any]]:
    """
    Extract transactions from a bank statement based on the specified bank type.
    
    Args:
        statement_text (str): The raw text content of the bank statement
        bank_type (str): The bank type ("BCP" or "DINERS")
        
    Returns:
        List[Dict]: List of transaction dictionaries with keys:
                   - transaction_date, description, transaction_type, currency, amount
                   
    Raises:
        ValueError: If bank_type is not supported or statement format doesn't match
    """
    # Route to appropriate extraction method based on bank type
    if bank_type.upper() == "BCP":
        return extract_bcp_transactions(statement_text)
    elif bank_type.upper() == "DINERS":
        return extract_diners_transactions(statement_text)
    else:
        raise ValueError(f"Unsupported bank type: {bank_type}. Supported banks: BCP, DINERS")

def extract_bcp_transactions(statement_text: str) -> List[Dict[str, Any]]:
    """
    Extract all transactions from a BCP VISA credit card statement.
    
    Args:
        statement_text (str): The raw text content of the BCP bank statement
        
    Returns:
        List[Dict]: List of transaction dictionaries
        
    Raises:
        ValueError: If statement format doesn't match BCP format
    """
    # Validate BCP format by looking for key indicators
    # Check for strong Diners Club indicators first
    if 'DINERS CLUB' in statement_text.upper():
        raise ValueError("Statement format does not match BCP VISA format. This appears to be a Diners Club statement.")
    
    # Look for BCP-specific patterns (more specific than just transaction types)
    bcp_indicators = ['BCP', 'BANCO DE CREDITO', 'VISA.*CONSUMO']
    if not any(indicator in statement_text.upper() for indicator in bcp_indicators):
        raise ValueError("Statement format does not match BCP VISA format")
        
    transactions = []
    
    # Split the text into lines for processing
    lines = statement_text.split('\n')
    
    # Pattern to match transaction lines with spacing analysis
    # Format: Date Date Description [Location] OPERATION_TYPE [spaces] Amount
    transaction_pattern = r'(\d{1,2}[A-Za-z]{3})\s+(\d{1,2}[A-Za-z]{3})\s+(.+?)\s+(CONSUMO|PAGO|CARGO)(.*)$'
    
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
    
    def determine_currency_and_amount(after_operation: str, description: str, full_line: str) -> tuple:
        """Determine currency and amount based on BCP location codes and explicit currency indicators"""
        # First, extract the amount (handles formats like: 123.45, .81, 1,234.56)
        amount_match = re.search(r'(?:\d{1,3}(?:,\d{3})*)?(?:\.\d+)?-?$', after_operation.strip())
        if not amount_match:
            return 'PEN', 0.0
            
        amount_str = amount_match.group()
        
        # Remove any negative sign for processing
        is_negative = amount_str.endswith('-')
        clean_amount = amount_str.replace('-', '').replace(',', '')
        
        # Convert to float
        try:
            amount = float(clean_amount)
        except ValueError:
            amount = 0.0
        
        # If it's a payment (negative), keep it negative
        if is_negative:
            amount = -amount
        
        # BCP Currency Detection Logic:
        # 1. Check for explicit USD mention in description
        if ' USD ' in description.upper() or description.upper().endswith(' USD'):
            return 'USD', amount
        
        # 2. Check for international location codes (non-PE country/state codes before CONSUMO)
        # Pattern: [description] [2-letter-code] CONSUMO [amount]
        # USD transactions: CA CONSUMO, WA CONSUMO, MN CONSUMO, DE CONSUMO, etc.
        # PEN transactions: PE CONSUMO
        
        # Look for location code pattern before CONSUMO
        location_match = re.search(r'\s([A-Z]{2})\s+CONSUMO\s', full_line)
        if location_match:
            location_code = location_match.group(1)
            if location_code != 'PE':  # Non-Peru location codes indicate USD
                return 'USD', amount
            else:  # PE indicates PEN (Peruvian Soles)
                return 'PEN', amount
        
        # 3. Fallback: Default to PEN for BCP VISA transactions
        # (Most transactions in Peru are in PEN unless explicitly marked otherwise)
        return 'PEN', amount
    
    # Process each line
    current_year = 2025  # Based on the statement dates
    
    # Patterns to exclude (summary/total lines and non-transaction entries)
    exclusion_patterns = [
        r'MONTO TOTAL',
        r'SUB.*TOTAL',
        r'TOTAL.*FACTURADO',
        r'SALDO.*ANTERIOR',
        r'NUEVO.*SALDO',
        r'PAGO.*MINIMO',
        r'FECHA.*VENCIMIENTO',
        r'LIMITE.*CREDITO',
        r'CREDITO.*DISPONIBLE',
        r'RESUMEN.*CUENTA',
        r'ESTADO.*CUENTA',
        r'^\s*CONSUMOS?\s*$',
        r'^\s*PAGOS?\s*$',
        r'^\s*ABONOS?\s*$',
        r'^\s*CARGOS?\s*$',
        r'^\s*[A-Z\s]+\s*$',  # Lines with only uppercase letters and spaces
        r'DETALLE.*MOVIMIENTOS',
        r'MOVIMIENTOS.*DEL.*PERIODO',
        r'FECHA.*PROCESO.*FECHA.*CONSUMO',
        r'PAGO BANCA MOVIL',  # Exclude mobile banking payments
        r'CUOTA DEL MES'      # Exclude monthly installment fees
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip lines that match exclusion patterns
        if any(re.search(pattern, line.upper()) for pattern in exclusion_patterns):
            continue
            
        # Match transaction pattern
        match = re.search(transaction_pattern, line)
        if match:
            process_date_str = match.group(1)
            consumption_date_str = match.group(2)
            description = match.group(3)
            operation_type = match.group(4)
            after_operation = match.group(5)  # Everything after the operation type
            
            # Additional validation: ensure description is a valid transaction description
            # Skip if description contains total/summary keywords
            desc_upper = description.upper()
            if any(keyword in desc_upper for keyword in [
                'TOTAL', 'SALDO', 'LIMITE', 'CREDITO DISPONIBLE', 'PAGO MINIMO',
                'VENCIMIENTO', 'RESUMEN', 'FACTURADO'
            ]):
                continue
                
            # Skip if description is too short or looks like a header
            if len(description.strip()) < 3:
                continue
            
            # Parse dates
            transaction_date = parse_date(consumption_date_str, current_year)
            
            # Clean description
            clean_desc = clean_description(description)
            
            # Determine currency and amount based on location codes and context
            currency, amount = determine_currency_and_amount(after_operation, clean_desc, line)
            
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

def extract_diners_transactions(statement_text: str) -> List[Dict[str, Any]]:
    """
    Extract all transactions from a Diners Club Peru credit card statement.
    
    Args:
        statement_text (str): The raw text content of the Diners Club statement
        
    Returns:
        List[Dict]: List of transaction dictionaries
        
    Raises:
        ValueError: If statement format doesn't match Diners Club format
    """
    # Validate Diners Club format by looking for key indicators
    # Check for BCP indicators first to give helpful error
    if any(indicator in statement_text.upper() for indicator in ['BCP', 'BANCO DE CREDITO']):
        raise ValueError("Statement format does not match Diners Club format. This appears to be a BCP statement.")
    
    if not any(indicator in statement_text.upper() for indicator in ['DINERS CLUB', 'CONSUMOS REVOLVENTES']):
        raise ValueError("Statement format does not match Diners Club format")
        
    transactions = []
    lines = statement_text.split('\n')
    
    # Spanish month mapping for Diners Club statements
    month_mapping = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08', 
        'SET': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    def extract_statement_year_and_period(text: str) -> tuple:
        """Extract year from statement date and determine billing period"""
        # Look for statement issue date like "05/01/2025"
        statement_date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
        
        if statement_date_match:
            statement_year = int(statement_date_match.group(3))
            
            # Look for billing period like "PERIODO FACTURADO DEL 19 NOV AL 18 DIC"
            period_match = re.search(r'PERIODO FACTURADO DEL.*?(\d{1,2})\s+([A-Z]{3}).*?(\d{1,2})\s+([A-Z]{3})', text)
            
            if period_match:
                start_month = month_mapping.get(period_match.group(2), '01')
                end_month = month_mapping.get(period_match.group(4), '12')
                
                # Handle year transition (Nov-Dec 2024 to Jan 2025)
                # If statement is issued in Jan 2025 but covers Nov-Dec, those are 2024
                if statement_year > 2024 and int(start_month) >= 11:  # Nov or Dec
                    period_year = statement_year - 1  # Previous year for Nov/Dec
                    return statement_year, period_year, period_year
                else:
                    # Normal case within same year
                    return statement_year, statement_year, statement_year
            else:
                # Fallback: use statement year for all transactions
                return statement_year, statement_year, statement_year
        else:
            # Fallback to current year if no date found
            return 2025, 2025, 2025
    
    def parse_diners_date(date_str: str, transaction_year: int) -> str:
        """Convert Diners date string like '23 NOV' to '2024-11-23'"""
        parts = date_str.strip().split()
        if len(parts) >= 2:
            day = parts[0].zfill(2)
            month_abbr = parts[1].upper()
            month = month_mapping.get(month_abbr, '01')
            return f"{transaction_year}-{month}-{day}"
        return f"{transaction_year}-01-01"  # Fallback
    
    def determine_diners_currency_by_context(transaction_line: str, amount: float) -> str:
        """Determine currency for single amount based on context clues"""
        line_upper = transaction_line.upper()
        
        # Strong USD indicators (international services/locations)
        strong_usd_clues = [
            'LONDON', ' USA ', ' US ', '.COM', 'AMAZON', 'NETFLIX', 'APPLE', 
            'GOOGLE', 'MICROSOFT', 'SPOTIFY', 'ALIEXPRESS', 'STEAM',
            'DISNEY', 'UBER', 'AIRBNB'
        ]
        
        # Strong PEN indicators (local Peruvian businesses)
        strong_pen_clues = [
            'LIMA PER', 'PERU', 'TOTTUS', 'PLAZA VEA', 'WONG', 'RIPLEY',
            'SAGA FALABELLA', 'CAD', 'MAKRO', 'METRO', 'PER'
        ]
        
        # Check for strong indicators first
        if any(clue in line_upper for clue in strong_usd_clues):
            return 'USD'
            
        if any(clue in line_upper for clue in strong_pen_clues):
            return 'PEN'
        
        # Fallback: amounts over 100 are more likely PEN, under 100 more likely USD
        # This is a heuristic based on typical spending patterns
        if amount >= 100:
            return 'PEN'
        else:
            return 'USD'
    
    def determine_diners_currency_and_amount(transaction_line: str) -> tuple:
        """
        Determine currency and amount based on column position in Diners Club statements.
        Logic: Last column is USD, second-to-last column is PEN.
        """
        # Find all decimal numbers in the line (potential amounts)
        amount_pattern = r'\b\d+\.\d{2}\b'
        amounts = re.findall(amount_pattern, transaction_line)
        
        if not amounts:
            return 'PEN', 0.0
        
        # For Diners Club: transactions have only one amount
        # Determine currency based on context and position
        amount_str = amounts[-1]  # Take the last amount found
        amount = float(amount_str)
        
        # Analyze the spacing/positioning to determine currency
        # Split by the amount to see what comes after
        parts = transaction_line.split(amount_str)
        if len(parts) > 1:
            after_amount = parts[-1]
            # Count spaces or check position - if there's significant trailing space, it's likely USD
            if len(after_amount.strip()) == 0 and len(after_amount) > 10:
                return 'USD', amount
            else:
                return 'PEN', amount
        
        # Additional context clues for currency detection
        line_upper = transaction_line.upper()
        
        # International indicators suggest USD
        international_clues = [
            'LONDON', 'USA', 'US', '.COM', 'AMAZON', 'NETFLIX', 'APPLE', 
            'GOOGLE', 'MICROSOFT', 'SPOTIFY', 'ALIEXPRESS'
        ]
        
        if any(clue in line_upper for clue in international_clues):
            return 'USD', amount
        
        # Peruvian indicators suggest PEN
        peruvian_clues = ['LIMA', 'PERU', 'PER', 'TOTTUS', 'PLAZA VEA', 'WONG']
        
        if any(clue in line_upper for clue in peruvian_clues):
            return 'PEN', amount
        
        # Default to PEN for local transactions
        return 'PEN', amount
    
    def clean_diners_description(desc: str) -> str:
        """Clean and standardize Diners Club description"""
        # Remove extra spaces and clean up
        desc = re.sub(r'\s+', ' ', desc.strip())
        # Remove common location codes and numbers at the end
        desc = re.sub(r'\s+\d{3,}$', '', desc)  # Remove trailing numbers like "826"
        return desc
    
    # Extract year information from statement
    statement_year, start_year, end_year = extract_statement_year_and_period(statement_text)
    
    # Find the CONSUMOS REVOLVENTES section
    in_consumos_section = False
    current_year = statement_year
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if we're entering the CONSUMOS REVOLVENTES section
        if 'CONSUMOS REVOLVENTES' in line.upper():
            in_consumos_section = True
            continue
        
        # Check if we're leaving the section (next section starts)
        if in_consumos_section and any(section in line.upper() for section in [
            'SUB TOTAL', 'CONSUMOS EN CUOTAS', 'INTERESES', 'COMISIONES', 'PAGOS/ABONOS'
        ]):
            if 'SUB TOTAL' in line.upper():
                continue  # Skip sub total lines but stay in section until next major section
            else:
                in_consumos_section = False
                continue
        
        # Process transaction lines within CONSUMOS REVOLVENTES section
        if in_consumos_section:
            # Skip lines that are clearly not transactions (like names, headers, totals)
            if line.upper() in ['DIEGO RIOS'] or len(line.split()) < 4:
                continue
            
            # Patterns to exclude (summary/total lines and non-transaction entries)
            exclusion_patterns = [
                r'MONTO TOTAL',
                r'SUB.*TOTAL',
                r'TOTAL.*FACTURADO',
                r'SALDO.*ANTERIOR',
                r'NUEVO.*SALDO',
                r'PAGO.*MINIMO',
                r'FECHA.*VENCIMIENTO',
                r'LIMITE.*CREDITO',
                r'CREDITO.*DISPONIBLE',
                r'RESUMEN.*CUENTA',
                r'ESTADO.*CUENTA',
                r'^\s*CONSUMOS?\s*$',
                r'^\s*PAGOS?\s*$',
                r'^\s*ABONOS?\s*$',
                r'^\s*CARGOS?\s*$',
                r'DETALLE.*MOVIMIENTOS',
                r'MOVIMIENTOS.*DEL.*PERIODO',
                r'FECHA.*PROCESO.*FECHA.*CONSUMO',
                r'TOTAL.*CONSUMOS',
                r'MONTO.*FACTURADO',
                r'^\s*TOTAL\s+[\d,]+\.?\d*\s*$',  # Lines that are just "TOTAL" followed by an amount
                r'^\s*[\d,]+\.?\d*\s*[\d,]+\.?\d*\s*$'  # Lines with only amounts (summary rows)
            ]
            
            # Skip lines that match exclusion patterns
            if any(re.search(pattern, line.upper()) for pattern in exclusion_patterns):
                continue
            
            # Pattern for Diners Club transactions: DD MMM DD MMM DESCRIPTION AMOUNT
            # Example: "05 MAY 05 MAY CAD DIRECTV 204.00"
            # More flexible pattern to capture the amount at the end
            transaction_pattern = r'^(\d{1,2}\s+[A-Z]{3})\s+(\d{1,2}\s+[A-Z]{3})\s+(.+?)\s+(\d+\.\d{2})(?:\s+(\d+\.\d{2}))?$'
            
            match = re.search(transaction_pattern, line)
            if match:
                process_date_str = match.group(1)  # "05 MAY"
                consumption_date_str = match.group(2)  # "05 MAY"  
                description_part = match.group(3).strip()  # "CAD DIRECTV"
                amount1_str = match.group(4)  # First amount (could be PEN)
                amount2_str = match.group(5) if match.group(5) else None  # Second amount (could be USD)
                
                # Additional validation: ensure description is a valid transaction description
                desc_upper = description_part.upper()
                if any(keyword in desc_upper for keyword in [
                    'TOTAL', 'SALDO', 'LIMITE', 'CREDITO DISPONIBLE', 'PAGO MINIMO',
                    'VENCIMIENTO', 'RESUMEN', 'FACTURADO', 'MONTO TOTAL'
                ]):
                    continue
                    
                # Skip if description is too short or looks like a summary
                if len(description_part.strip()) < 3:
                    continue
                
                # Determine currency based on column position
                # If there are two amounts, first is PEN, second is USD
                # If there's only one amount, determine by position/context
                if amount2_str:
                    # Two amounts present - first is PEN, second is USD
                    # For now, let's extract both as separate transactions or choose based on non-zero
                    pen_amount = float(amount1_str)
                    usd_amount = float(amount2_str)
                    
                    # Choose the non-zero amount or the larger amount
                    if pen_amount > 0 and usd_amount == 0:
                        currency, amount = 'PEN', pen_amount
                    elif usd_amount > 0 and pen_amount == 0:
                        currency, amount = 'USD', usd_amount  
                    elif pen_amount > 0 and usd_amount > 0:
                        # Both amounts present - this shouldn't happen normally, choose PEN
                        currency, amount = 'PEN', pen_amount
                    else:
                        currency, amount = 'PEN', pen_amount  # Default to PEN
                else:
                    # Single amount - determine currency by context
                    amount = float(amount1_str)
                    currency = determine_diners_currency_by_context(line, amount)
                
                # Determine the year for this transaction based on month
                consumption_month = consumption_date_str.split()[1].upper()
                
                # Year logic: if statement covers previous year months, use correct year
                if consumption_month in ['NOV', 'DIC'] and start_year < statement_year:
                    transaction_year = start_year  # Use period year for Nov/Dec
                elif consumption_month in ['ENE', 'FEB'] and start_year < statement_year:
                    transaction_year = statement_year  # Use statement year for Jan/Feb  
                else:
                    transaction_year = start_year  # Use period year as default
                
                # Parse the transaction date (use consumption date)
                transaction_date = parse_diners_date(consumption_date_str, transaction_year)
                
                # Clean the description
                clean_desc = clean_diners_description(description_part)
                
                transaction = {
                    'transaction_date': transaction_date,
                    'description': clean_desc,
                    'transaction_type': 'Purchase',  # All CONSUMOS REVOLVENTES are purchases
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

def process_bank_statement_pdf(pdf_path: str, bank_type: str = "BCP") -> List[Dict[str, Any]]:
    """
    Process a bank statement PDF and extract all transactions based on bank type.
    
    Args:
        pdf_path (str): Path to the PDF statement file
        bank_type (str): The bank type ("BCP" or "DINERS")
        
    Returns:
        List[Dict]: List of transaction dictionaries
        
    Raises:
        ValueError: If bank_type is not supported or statement format doesn't match
    """
    # Extract text from PDF
    statement_text = extract_text_from_pdf(pdf_path)
    
    # Extract transactions from the text based on bank type
    transactions = extract_transactions_from_statement(statement_text, bank_type)
    
    return transactions

# Example usage with command line argument or file selection:
if __name__ == "__main__":
    # Check if PDF path and bank type are provided as command line arguments
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]
        bank_type = sys.argv[2] if len(sys.argv) > 2 else "BCP"
    else:
        # Interactive mode
        pdf_file_path = input("Enter the path to your bank statement PDF: ").strip()
        bank_type = input("Enter bank type (BCP or DINERS) [BCP]: ").strip() or "BCP"
        
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
        
        # Validate bank type
        if bank_type.upper() not in ["BCP", "DINERS"]:
            print(f"Error: Unsupported bank type '{bank_type}'. Supported: BCP, DINERS")
            sys.exit(1)
        
        print(f"Processing {bank_type.upper()} statement: {pdf_file_path}")
        
        # Process the PDF and extract transactions
        transactions = process_bank_statement_pdf(pdf_file_path, bank_type)
        
        # Output clean JSON with all transactions
        print(json.dumps(transactions, indent=2, ensure_ascii=False))
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}", file=sys.stderr)
        sys.exit(1)