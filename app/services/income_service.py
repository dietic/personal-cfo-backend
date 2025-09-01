from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List
import logging
import pytz

from app.models.income import Income
from app.models.transaction import Transaction
from app.schemas.income import IncomeCreate

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
            Income.recurrence_day.isnot(None)
        ).all()
        
        created_count = 0
        
        for income in recurring_incomes:
            # Check if today is the recurrence day
            if today_peru.day != income.recurrence_day:
                continue
                
            # Check if this recurring income has already been processed today
            if income.last_processed_date == today_peru:
                continue
                
            # Create transaction for this recurring income
            transaction = Transaction(
                card_id=income.card_id,
                merchant=f"Recurring Income: {income.description}",
                amount=income.amount,
                currency=income.currency,
                category="Income",  # Use "Income" category as per requirements
                transaction_date=today_peru,
                description=f"Recurring income: {income.description}",
                is_recurring_income=True,
                recurring_income_id=income.id
            )
            
            self.db.add(transaction)
            
            # Update last processed date
            income.last_processed_date = today_peru
            
            created_count += 1
            
            logger.info(f"Created recurring transaction: {income.description} - {income.amount} {income.currency} for {today_peru}")
        
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
            income_date=target_date,
            is_recurring=True,
            recurring_day=recurring_income.recurring_day,
            category=recurring_income.category
        )
        
        self.db.add(new_income)
        self.db.commit()
        self.db.refresh(new_income)
        
        return new_income