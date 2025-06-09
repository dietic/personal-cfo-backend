import openai
from typing import Optional, Dict, Any, List
from app.core.config import settings
import json

class AIService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def categorize_transaction(self, merchant: str, amount: float, description: str = "", currency: str = "USD") -> Dict[str, Any]:
        """Categorize a transaction using OpenAI"""
        prompt = f"""
        Categorize this financial transaction into one of these categories:
        - food
        - housing
        - transport
        - entertainment
        - healthcare
        - shopping
        - utilities
        - education
        - other
        
        Transaction details:
        Merchant: {merchant}
        Amount: {amount} {currency}
        Description: {description}
        
        Respond with a JSON object containing:
        - category: the category name
        - confidence: confidence score from 0.0 to 1.0
        - reasoning: brief explanation
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial categorization expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                return {
                    "category": result.get("category", "other"),
                    "confidence": result.get("confidence", 0.5),
                    "reasoning": result.get("reasoning", "")
                }
            else:
                raise ValueError("Empty response from AI")
        except Exception as e:
            return {
                "category": "other",
                "confidence": 0.0,
                "reasoning": f"Error in categorization: {str(e)}"
            }

    def analyze_statement_and_generate_insights(self, transactions_data: List[Dict[str, Any]], statement_month: str, user_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Analyze a statement and generate comprehensive insights, trends, and alerts"""
        
        # Calculate current statement statistics
        total_spending = sum(tx.get('amount', 0) for tx in transactions_data)
        transaction_count = len(transactions_data)
        currencies = list(set(tx.get('currency', 'USD') for tx in transactions_data))
        
        # Group by category for analysis
        category_spending = {}
        for tx in transactions_data:
            category = tx.get('category', 'other')
            amount = tx.get('amount', 0)
            currency = tx.get('currency', 'USD')
            
            key = f"{category}_{currency}"
            if key not in category_spending:
                category_spending[key] = 0
            category_spending[key] += amount

        prompt = f"""
        You are an expert financial advisor AI. Analyze this bank statement data and provide comprehensive insights.

        CURRENT STATEMENT DATA (Month: {statement_month}):
        - Total transactions: {transaction_count}
        - Total spending: ${total_spending:.2f}
        - Currencies found: {currencies}
        - Category breakdown: {json.dumps(category_spending, indent=2)}
        - Detailed transactions: {json.dumps(transactions_data, indent=2)}

        HISTORICAL USER DATA (Last 50 transactions):
        {json.dumps(user_history[-50:] if user_history else [], indent=2)}

        Please provide a comprehensive financial analysis including:

        1. **SPENDING SUMMARY**: Overall spending patterns for this month
        2. **TREND ANALYSIS**: Compare current month vs historical patterns
        3. **ALERTS**: Identify unusual or concerning transactions/patterns
        4. **CATEGORY INSIGHTS**: Deep dive into spending by category
        5. **RECOMMENDATIONS**: Actionable advice for better financial management
        6. **ALERTS FOR FUTURE**: Set up monitoring for specific patterns

        Focus on:
        - Unusual spending increases/decreases
        - New merchants or categories
        - Large transactions that deviate from patterns
        - Budget recommendations based on spending trends
        - Savings opportunities
        - Risk factors (overspending, new debt patterns)

        Respond with this JSON structure:
        {{
            "summary": {{
                "total_spending": {total_spending},
                "transaction_count": {transaction_count},
                "avg_transaction": "calculated average",
                "currencies": {currencies},
                "month": "{statement_month}",
                "key_insights": ["insight1", "insight2", "insight3"]
            }},
            "trends": {{
                "spending_change": {{
                    "percentage": "vs last month",
                    "direction": "increase/decrease/stable",
                    "analysis": "detailed explanation"
                }},
                "category_changes": [
                    {{
                        "category": "category_name",
                        "change": "percentage_change",
                        "significance": "high/medium/low",
                        "explanation": "why this matters"
                    }}
                ],
                "new_patterns": ["list of new spending patterns detected"]
            }},
            "alerts": [
                {{
                    "type": "unusual_spending/large_transaction/new_merchant/budget_exceeded",
                    "severity": "high/medium/low",
                    "title": "Alert title",
                    "description": "Detailed alert description",
                    "transaction_details": "specific transaction if applicable",
                    "recommendation": "what user should do"
                }}
            ],
            "category_insights": [
                {{
                    "category": "category_name",
                    "amount": "total_spent",
                    "percentage_of_total": "percentage",
                    "trend": "increasing/decreasing/stable",
                    "insight": "detailed analysis",
                    "recommendation": "specific advice"
                }}
            ],
            "recommendations": [
                {{
                    "type": "budget/savings/debt/investment",
                    "priority": "high/medium/low",
                    "title": "Recommendation title",
                    "description": "Detailed recommendation",
                    "potential_impact": "expected financial impact",
                    "action_steps": ["step1", "step2", "step3"]
                }}
            ],
            "future_monitoring": [
                {{
                    "alert_type": "spending_limit/merchant_watch/category_budget",
                    "criteria": "specific criteria to monitor",
                    "threshold": "specific threshold value",
                    "frequency": "weekly/monthly",
                    "description": "what to watch for"
                }}
            ]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert financial advisor AI with deep knowledge of spending patterns, budgeting, and financial planning. Always provide actionable, practical advice. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                return result
            else:
                raise ValueError("Empty response from AI")
        except json.JSONDecodeError as e:
            return {
                "summary": {"total_spending": total_spending, "error": "JSON parsing failed"},
                "trends": {"spending_change": {"analysis": "Unable to analyze trends"}},
                "alerts": [{"type": "system_error", "severity": "low", "title": "Analysis Error", "description": f"Could not fully analyze statement: {str(e)}"}],
                "category_insights": [],
                "recommendations": [{"type": "system", "priority": "low", "title": "Manual Review", "description": "Please review this statement manually due to analysis error"}],
                "future_monitoring": []
            }
        except Exception as e:
            return {
                "summary": {"total_spending": total_spending, "error": str(e)},
                "trends": {"spending_change": {"analysis": "Analysis failed"}},
                "alerts": [{"type": "system_error", "severity": "high", "title": "Analysis Failed", "description": f"Statement analysis error: {str(e)}"}],
                "category_insights": [],
                "recommendations": [],
                "future_monitoring": []
            }

    def analyze_spending_patterns(self, transactions_data: list) -> Dict[str, Any]:
        """Analyze spending patterns and provide insights"""
        prompt = f"""
        Analyze these spending patterns and provide insights:
        
        Transaction data: {json.dumps(transactions_data[:50])}  # Limit data size
        
        Provide insights about:
        1. Overspending patterns
        2. Unusual transactions
        3. Budget recommendations
        
        Respond with JSON containing an array of insights with:
        - type: "overspending", "anomaly", "suggestion"
        - title: brief title
        - description: detailed description
        - category: relevant category
        - confidence: confidence score 0.0-1.0
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial advisor AI. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                return result
            else:
                raise ValueError("Empty response from AI")
        except Exception as e:
            return {
                "insights": [],
                "error": str(e)
            }

    def detect_anomalies(self, transaction_data: Dict[str, Any], user_history: list) -> Dict[str, Any]:
        """Detect anomalous transactions"""
        prompt = f"""
        Analyze this transaction for anomalies based on user's spending history:
        
        New transaction: {json.dumps(transaction_data)}
        Recent history: {json.dumps(user_history[-20:])}  # Last 20 transactions
        
        Determine if this transaction is anomalous and respond with JSON:
        - is_anomaly: boolean
        - anomaly_type: "amount", "merchant", "category", "frequency"
        - confidence: 0.0-1.0
        - explanation: brief explanation
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a fraud detection AI. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                return result
            else:
                raise ValueError("Empty response from AI")
        except Exception as e:
            return {
                "is_anomaly": False,
                "confidence": 0.0,
                "explanation": f"Error in anomaly detection: {str(e)}"
            }
    
    def categorize_transactions_batch(
        self, 
        transactions: List[Dict[str, Any]], 
        available_categories: List[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """Categorize multiple transactions in a single API call for efficiency"""
        
        if not transactions:
            return []
        
        # Prepare transactions for batch processing
        transactions_text = []
        for i, tx in enumerate(transactions):
            tx_text = f"{i+1}. Merchant: {tx.get('merchant', '')}, Amount: {tx.get('amount', 0)}, Description: {tx.get('description', '')}"
            transactions_text.append(tx_text)
        
        categories_str = ", ".join(available_categories)
        
        prompt = f"""
        Categorize these {len(transactions)} financial transactions into the most appropriate categories.
        
        Available categories: {categories_str}
        
        Transactions:
        {chr(10).join(transactions_text)}
        
        For each transaction, respond with a JSON array where each element contains:
        - category: the best matching category name from the available list
        - confidence: confidence score from 0.0 to 1.0
        - reasoning: brief explanation for the categorization
        
        Respond ONLY with a valid JSON array with {len(transactions)} elements.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial categorization expert. Always respond with valid JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            if content:
                results = json.loads(content)
                
                # Validate results length matches input
                if len(results) != len(transactions):
                    raise ValueError(f"Expected {len(transactions)} results, got {len(results)}")
                
                # Validate and clean up results
                cleaned_results = []
                for i, result in enumerate(results):
                    if isinstance(result, dict):
                        category = result.get("category", "Other")
                        # Ensure category is in available list
                        if category not in available_categories:
                            category = "Other"
                        
                        cleaned_results.append({
                            "category": category,
                            "confidence": float(result.get("confidence", 0.5)),
                            "reasoning": result.get("reasoning", "")
                        })
                    else:
                        # Fallback for malformed results
                        cleaned_results.append({
                            "category": "Other",
                            "confidence": 0.0,
                            "reasoning": "Malformed AI response"
                        })
                
                return cleaned_results
            else:
                raise ValueError("Empty response from AI")
                
        except Exception as e:
            # Return fallback results for all transactions
            return [{
                "category": "Other",
                "confidence": 0.0,
                "reasoning": f"Batch categorization error: {str(e)}"
            } for _ in transactions]
    
    def categorize_single_transaction(
        self, 
        transaction: Dict[str, Any], 
        available_categories: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Categorize a single transaction with user's custom categories"""
        
        categories_str = ", ".join(available_categories)
        merchant = transaction.get('merchant', '')
        amount = transaction.get('amount', 0)
        description = transaction.get('description', '')
        
        prompt = f"""
        Categorize this financial transaction into the most appropriate category.
        
        Available categories: {categories_str}
        
        Transaction details:
        Merchant: {merchant}
        Amount: {amount}
        Description: {description}
        
        Respond with a JSON object containing:
        - category: the best matching category name from the available list
        - confidence: confidence score from 0.0 to 1.0
        - reasoning: brief explanation for the categorization
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial categorization expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                category = result.get("category", "Other")
                
                # Ensure category is in available list
                if category not in available_categories:
                    category = "Other"
                
                return {
                    "category": category,
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", "")
                }
            else:
                raise ValueError("Empty response from AI")
                
        except Exception as e:
            return {
                "category": "Other",
                "confidence": 0.0,
                "reasoning": f"Error in categorization: {str(e)}"
            }
