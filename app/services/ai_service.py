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
        """Analyze a statement and generate insights, tips, and alerts"""
        prompt = f"""
        Analyze this bank statement for month {statement_month} and provide financial insights.
        
        Statement transactions: {json.dumps(transactions_data)}
        
        User's recent transaction history: {json.dumps(user_history[-50:] if user_history else [])}
        
        Provide comprehensive analysis including:
        1. Spending summary for this month
        2. Notable patterns or changes compared to history
        3. Alerts for unusual transactions
        4. Budget recommendations
        5. Tips for better financial management
        6. Currency-specific insights (if mixed currencies detected)
        
        Respond with JSON containing:
        - summary: overall spending summary
        - insights: array of insights with type, title, description, category, priority (1-5)
        - alerts: array of alerts for unusual activity
        - tips: array of actionable financial tips
        - recommendations: budget and saving recommendations
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a expert financial advisor AI. Provide practical, actionable advice. Always respond with valid JSON."},
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
                "summary": "Error analyzing statement",
                "insights": [],
                "alerts": [],
                "tips": [],
                "recommendations": [],
                "error": str(e)
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
