"""
AI Categorization Service - Uses OpenAI to categorize transactions into Spanish categories
"""

import openai
import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AICategorizer:
    """Use AI only for categorizing transactions, not for extraction"""
    
    def __init__(self):
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def categorize_transactions_batch(
        self, 
        transactions: List[Dict[str, Any]], 
        spanish_categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Categorize a batch of transactions using AI
        
        Args:
            transactions: List of transaction dictionaries
            spanish_categories: List of available Spanish categories
            
        Returns:
            List of transactions with added 'category' field
        """
        if not transactions:
            return []
        
        try:
            # Prepare transaction data for AI categorization
            transaction_data = []
            for txn in transactions:
                transaction_data.append({
                    "description": txn.get('description', ''),
                    "merchant": txn.get('merchant', ''),
                    "amount": txn.get('amount', 0),
                    "currency": txn.get('currency', 'USD')
                })
            
            # Create the categorization prompt
            categories_list = ", ".join(f'"{cat}"' for cat in spanish_categories)
            
            prompt = f"""
You are an expert at categorizing financial transactions. Categorize each transaction using ONLY the provided Spanish categories.

Available categories: [{categories_list}]

Transactions to categorize:
{json.dumps(transaction_data, indent=2)}

For each transaction, determine the most appropriate category based on the merchant/description.

Rules:
- Use ONLY categories from the provided list
- If uncertain, use "Misc" as fallback
- Consider the merchant name and transaction description
- Common patterns:
  - Supermarkets/groceries → "Supermercado"
  - Restaurants/food → "Comida Rapida" 
  - Gas stations → "Combustible"
  - Entertainment services → "Entretenimiento"
  - Medical/pharmacy → "Salud"
  - Bank transfers → "Transferencias"

Return a JSON array with the same transactions but with an added "category" field:
[
  {{
    "description": "...",
    "merchant": "...",
    "amount": 123.45,
    "currency": "USD",
    "category": "Supermercado"
  }}
]
"""

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert financial transaction categorizer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if content:
                categorized_data = json.loads(content)
                
                # Merge the categories back into the original transactions
                for i, txn in enumerate(transactions):
                    if i < len(categorized_data):
                        category = categorized_data[i].get('category', 'Misc')
                        # Validate category is in allowed list
                        if category not in spanish_categories:
                            category = 'Misc'
                        txn['category'] = category
                    else:
                        txn['category'] = 'Misc'
                
                logger.info(f"Successfully categorized {len(transactions)} transactions")
                return transactions
            else:
                # Fallback - assign Misc to all
                for txn in transactions:
                    txn['category'] = 'Misc'
                logger.warning("Empty AI response, using fallback categorization")
                return transactions
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in AI categorization: {e}")
            # Fallback - assign Misc to all
            for txn in transactions:
                txn['category'] = 'Misc'
            return transactions
            
        except Exception as e:
            logger.error(f"AI categorization failed: {e}")
            # Fallback - assign Misc to all
            for txn in transactions:
                txn['category'] = 'Misc'
            return transactions
    
    def categorize_single_transaction(
        self, 
        transaction: Dict[str, Any], 
        spanish_categories: List[str]
    ) -> str:
        """
        Categorize a single transaction
        
        Args:
            transaction: Transaction dictionary
            spanish_categories: List of available categories
            
        Returns:
            Category string
        """
        categorized = self.categorize_transactions_batch([transaction], spanish_categories)
        return categorized[0].get('category', 'Misc') if categorized else 'Misc'
