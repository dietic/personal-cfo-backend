from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List
import logging
import pytz
from dateutil.relativedelta import relativedelta

from app.models.income import Income
from app.models.transaction import Transaction
from app.schemas.income import IncomeCreate
from app.services.category_service import CategoryService

logger = logging.getLogger(__name__)

class IncomeService:
    def __init__(self, db: Session):
        self.db = db
    
    def process_recurring_incomes(self) -> int:
        """
        Process recurring incomes and create transactions for due dates.
        Creates transaction records for recurring incomes that are due.
        Returns the number of new transaction records created.
        """
        # Get current date in Peru timezone (UTC-5)
        peru_tz = pytz.timezone('America/Lima')
        now_peru = datetime.now(peru_tz)
        today_peru = now_peru.date()
        
        # Get all recurring incomes
        recurring_incomes = self.db.query(Income).filter(
            Income.is_recurring == True,
            Income.recurring_day.isnot(None)
        ).all()
        
        created_count = 0
        
        for income in recurring_incomes:
            # Check if today is the recurrence day
            if today_peru.day != income.recurring_day:
                continue
                
            # Check if this recurring income has already been processed today
            if income.last_processed_date == today_peru:
                continue
                
            # Validate income amount is positive before creating transaction
            income.validate_amount()
            
            # Get the system Income category
            income_category = CategoryService.get_income_category(self.db, income.user_id)
            
            # Create transaction for this recurring income
            transaction = Transaction(
                card_id=income.card_id,
                merchant=income.source,
                amount=income.amount,
                currency=income.currency,
                category=income_category.name,  # Use database Income category
                transaction_date=today_peru,
                description=f"Recurring income: {income.description}"
            )
            
            self.db.add(transaction)
            
            # Update last processed date
            income.last_processed_date = today_peru
            
            created_count += 1
            
            logger.info(f"Created recurring transaction: {income.source} - {income.amount} {income.currency} for {today_peru}")
        
        if created_count > 0:
            self.db.commit()
            logger.info(f"Created {created_count} recurring transaction records for {today_peru}")
        
        return created_count
    
    def get_user_recurring_incomes(self, user_id: str) -> List[Income]:
        """Get all recurring incomes for a user"""
        return self.db.query(Income).filter(
            Income.user_id == user_id,
            Income.is_recurring == True
        ).all()
    
    def get_user_incomes_by_period(self, user_id: str, start_date: date, end_date: date) -> List[Income]:
        """Get user incomes within a date range"""
        return self.db.query(Income).filter(
            Income.user_id == user_id,
            Income.income_date >= start_date,
            Income.income_date <= end_date
        ).order_by(Income.income_date.desc()).all()
    
    def get_total_income_by_period(self, user_id: str, start_date: date, end_date: date) -> float:
        """Calculate total income for a user within a date range"""
        result = self.db.query(Income).filter(
            Income.user_id == user_id,
            Income.income_date >= start_date,
            Income.income_date <= end_date
        ).all()
        
        return sum(float(income.amount) for income in result)
    
    def create_income_from_recurring(self, recurring_income: Income, target_date: date) -> Income:
        """Create a new income record from a recurring income template"""
        new_income = Income(
            user_id=recurring_income.user_id,
            amount=recurring_income.amount,
            currency=recurring_income.currency,
            description=recurring_income.description,
            source=recurring_income.source,
            income_date=target_date,
            is_recurring=True,
            recurring_day=recurring_income.recurring_day
        )
        
        self.db.add(new_income)
        self.db.commit()
        self.db.refresh(new_income)
        
        return new_income
    
    def create_past_recurring_transactions(self, income: Income) -> int:
        """
        Create transactions for past months when a recurring income is created.
        For example: if created on Sept 7th with income_date July 31st,
        creates transactions for July 31st and August 31st.
        """
        if not income.is_recurring or not income.recurring_day:
            return 0
            
        peru_tz = pytz.timezone('America/Lima')
        now_peru = datetime.now(peru_tz)
        today_peru = now_peru.date()
        
        created_count = 0
        
        # Start from the original income date
        current_date = income.income_date
        
        # Get the system Income category
        income_category = CategoryService.get_income_category(self.db, income.user_id)
        
        # Create transactions for all months from income_date up to and including current month
        # if we haven't passed the recurring day yet
        while current_date <= today_peru:
            # Check if we should create transaction for this month
            # For past months: always create
            # For current month: only create if we haven't passed the recurring day yet
            should_create = (
                current_date < today_peru or  # Past months
                (current_date.year == today_peru.year and 
                 current_date.month == today_peru.month and 
                 today_peru.day >= income.recurring_day)  # Current month if day >= recurring day
            )
            
            # Skip the original transaction (it will be created separately)
            if should_create and current_date != income.income_date:
                transaction = Transaction(
                    card_id=income.card_id,
                    merchant=income.source,  # Use income source as merchant
                    amount=income.amount,
                    currency=income.currency,
                    category=income_category.name,
                    transaction_date=current_date,
                    description=f"Recurring income: {income.description}"
                )
                
                self.db.add(transaction)
                created_count += 1
                logger.info(f"Created past recurring transaction: {income.source} - {income.amount} {income.currency} for {current_date}")
            
            # Move to next month, always trying to get to the recurring day
            next_date = current_date + relativedelta(months=1)
            
            # Try to set to the recurring day
            try:
                next_date = next_date.replace(day=income.recurring_day)
            except ValueError:
                # If the day doesn't exist in this month (e.g., Feb 31), use last day of month
                next_date = next_date + relativedelta(day=31)  # This will give us the last day
                
            current_date = next_date
        
        if created_count > 0:
            self.db.commit()
            logger.info(f"Created {created_count} past recurring transaction records")
        
        return created_count