from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging
import pytz

from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.pnl import PnLSummary, PnLCategorySummary, TransactionType
from app.core.config import settings

logger = logging.getLogger(__name__)

class PnLService:
    """Service for Profit & Loss calculations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_pnl(
        self, 
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        base_currency: Optional[str] = None
    ) -> PnLSummary:
        """
        Calculate Profit & Loss for a user within a date range
        """
        # Set default dates if not provided
        if start_date is None:
            start_date = date.today().replace(day=1)  # First day of current month
        if end_date is None:
            end_date = date.today()
        
        # Get user's base currency if not provided
        if base_currency is None:
            user = self.db.query(User).filter(User.id == user_id).first()
            base_currency = user.preferred_currency.value if user and user.preferred_currency else "USD"
        
        # Get transactions for the period
        transactions = self._get_transactions_for_period(user_id, start_date, end_date)
        
        # Filter and categorize transactions
        income_transactions, expense_transactions = self._categorize_transactions(transactions)
        
        # Convert amounts to base currency
        income_base = self._convert_to_base_currency(income_transactions, base_currency)
        expense_base = self._convert_to_base_currency(expense_transactions, base_currency)
        
        # Calculate totals
        total_income = sum(tx['amount_base'] for tx in income_base)
        total_expenses = sum(tx['amount_base'] for tx in expense_base)
        net_amount = total_income - total_expenses
        savings_rate = (net_amount / total_income * 100) if total_income > 0 else 0
        
        # Group by category
        income_by_category = self._group_by_category(income_base)
        expenses_by_category = self._group_by_category(expense_base)
        
        # Check for unclassified income
        has_unclassified_income = any(
            tx['category'] is None or tx['category'].strip() == '' 
            for tx in income_base
        )
        unclassified_income_count = sum(
            1 for tx in income_base 
            if tx['category'] is None or tx['category'].strip() == ''
        )
        
        return PnLSummary(
            period_start=start_date,
            period_end=end_date,
            base_currency=base_currency,
            total_income=total_income,
            total_expenses=total_expenses,
            net_amount=net_amount,
            savings_rate=float(savings_rate),
            income_by_category=income_by_category,
            expenses_by_category=expenses_by_category,
            exchange_rate_policy="transaction_date_rate_or_period_average",
            is_profitable=net_amount >= 0,
            has_unclassified_income=has_unclassified_income,
            unclassified_income_count=unclassified_income_count
        )
    
    def _get_transactions_for_period(self, user_id: str, start_date: date, end_date: date) -> List[Transaction]:
        """Get transactions for the period, excluding internal transfers and payments"""
        # Get all transactions for the user in the period
        transactions = self.db.query(Transaction).join(
            Transaction.card
        ).filter(
            and_(
                Transaction.card.has(user_id=user_id),
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            )
        ).all()
        
        # Filter out internal transactions
        filtered_transactions = []
        for tx in transactions:
            # Exclude transfers between own accounts, credit card payments, top-ups
            if self._is_internal_transaction(tx):
                continue
            filtered_transactions.append(tx)
        
        return filtered_transactions
    
    def _is_internal_transaction(self, transaction: Transaction) -> bool:
        """Check if transaction should be excluded as internal"""
        # Exclude based on merchant patterns
        exclude_patterns = [
            'transfer', 'payment', 'top-up', 'top up', 'deposit',
            'pago', 'transferencia', 'recarga', 'abono'
        ]
        
        merchant_lower = (transaction.merchant or '').lower()
        description_lower = (transaction.description or '').lower()
        
        # Check if transaction matches exclusion patterns
        for pattern in exclude_patterns:
            if pattern in merchant_lower or pattern in description_lower:
                return True
        
        return False
    
    def _categorize_transactions(self, transactions: List[Transaction]) -> Tuple[List[Dict], List[Dict]]:
        """Categorize transactions as income or expense"""
        income_transactions = []
        expense_transactions = []
        
        for tx in transactions:
            tx_data = {
                'id': str(tx.id),
                'date': tx.transaction_date,
                'description': tx.description,
                'amount_original': tx.amount,
                'currency_original': tx.currency,
                'category': tx.category,
                'merchant': tx.merchant
            }
            
            # Categorize as income or expense
            if tx.category and tx.category.lower() == 'income':
                income_transactions.append(tx_data)
            else:
                # For expenses, we use absolute value
                tx_data['amount_original'] = abs(tx.amount)
                expense_transactions.append(tx_data)
        
        return income_transactions, expense_transactions
    
    def _convert_to_base_currency(self, transactions: List[Dict], base_currency: str) -> List[Dict]:
        """Convert transaction amounts to base currency"""
        # TODO: Implement proper currency conversion using stored FX rates
        # For now, assume 1:1 conversion for same currency
        converted_transactions = []
        
        for tx in transactions:
            if tx['currency_original'] == base_currency:
                tx['amount_base'] = tx['amount_original']
            else:
                # Placeholder for actual FX conversion
                # This should use stored exchange rates from transaction date
                tx['amount_base'] = tx['amount_original']  # 1:1 assumption
            
            converted_transactions.append(tx)
        
        return converted_transactions
    
    def _group_by_category(self, transactions: List[Dict]) -> List[PnLCategorySummary]:
        """Group transactions by category and calculate summaries"""
        category_totals = {}
        category_counts = {}
        
        for tx in transactions:
            category = tx['category'] or 'Uncategorized'
            amount = tx['amount_base']
            
            if category not in category_totals:
                category_totals[category] = Decimal('0')
                category_counts[category] = 0
            
            category_totals[category] += amount
            category_counts[category] += 1
        
        # Calculate total for percentage calculation
        total_amount = sum(category_totals.values())
        
        # Create category summaries
        category_summaries = []
        for category, amount in category_totals.items():
            percentage = (amount / total_amount * 100) if total_amount > 0 else 0
            
            category_summaries.append(PnLCategorySummary(
                category=category,
                amount_base=amount,
                percentage=float(percentage),
                transaction_count=category_counts[category]
            ))
        
        # Sort by amount descending
        category_summaries.sort(key=lambda x: x.amount_base, reverse=True)
        
        return category_summaries