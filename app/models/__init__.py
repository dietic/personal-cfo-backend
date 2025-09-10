# Import all models here for Alembic
from app.models.user import User
from app.models.bank_provider import BankProvider
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.recurring_service import RecurringService
from app.models.budget import Budget
from app.models.statement import Statement
from app.models.category import Category
from app.models.category_keyword import CategoryKeyword
from app.models.alert import Alert
from app.models.user_excluded_keyword import UserExcludedKeyword
from app.models.user_keyword_rule import UserKeywordRule
from app.models.income import Income
from app.models.merchant import Merchant

__all__ = [
    "User",
    "BankProvider",
    "Card",
    "Transaction",
    "RecurringService",
    "Budget",
    "Statement",
    "Category",
    "CategoryKeyword",
    "Alert",
    "UserExcludedKeyword",
    "UserKeywordRule",
    "Income",
    "Merchant",
]
