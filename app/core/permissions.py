from enum import Enum
from typing import Dict, List
from app.models.user import UserTypeEnum

class Permission(Enum):
    # Basic permissions
    VIEW_PROFILE = "view_profile"
    EDIT_PROFILE = "edit_profile"
    
    # Transaction permissions
    VIEW_TRANSACTIONS = "view_transactions"
    ADD_TRANSACTIONS = "add_transactions"
    EDIT_TRANSACTIONS = "edit_transactions"
    DELETE_TRANSACTIONS = "delete_transactions"
    
    # Budget permissions
    VIEW_BUDGETS = "view_budgets"
    CREATE_BUDGETS = "create_budgets"
    EDIT_BUDGETS = "edit_budgets"
    DELETE_BUDGETS = "delete_budgets"
    
    # Category permissions
    VIEW_CATEGORIES = "view_categories"
    CREATE_CATEGORIES = "create_categories"
    EDIT_CATEGORIES = "edit_categories"
    DELETE_CATEGORIES = "delete_categories"
    
    # Card permissions
    VIEW_CARDS = "view_cards"
    ADD_CARDS = "add_cards"
    EDIT_CARDS = "edit_cards"
    DELETE_CARDS = "delete_cards"
    
    # Recurring service permissions
    VIEW_RECURRING_SERVICES = "view_recurring_services"
    CREATE_RECURRING_SERVICES = "create_recurring_services"
    EDIT_RECURRING_SERVICES = "edit_recurring_services"
    DELETE_RECURRING_SERVICES = "delete_recurring_services"
    
    # Alert permissions
    VIEW_ALERTS = "view_alerts"
    CREATE_ALERTS = "create_alerts"
    EDIT_ALERTS = "edit_alerts"
    DELETE_ALERTS = "delete_alerts"
    
    # Statement permissions
    VIEW_STATEMENTS = "view_statements"
    UPLOAD_STATEMENTS = "upload_statements"
    DELETE_STATEMENTS = "delete_statements"
    
    # Advanced features
    EXPORT_DATA = "export_data"
    ADVANCED_REPORTS = "advanced_reports"
    BULK_OPERATIONS = "bulk_operations"
    API_ACCESS = "api_access"
    
    # Admin permissions
    VIEW_ALL_USERS = "view_all_users"
    EDIT_ALL_USERS = "edit_all_users"
    DELETE_ALL_USERS = "delete_all_users"
    VIEW_SYSTEM_METRICS = "view_system_metrics"
    MANAGE_SYSTEM_SETTINGS = "manage_system_settings"

# Define limits for each user type
USER_LIMITS: Dict[UserTypeEnum, Dict[str, int]] = {
    UserTypeEnum.FREE: {
        "max_cards": 2,
        "max_budgets": 3,
        "max_recurring_services": 5,
        "max_categories": 10,
        "max_monthly_transactions": 100,
        "data_retention_months": 12,
    },
    UserTypeEnum.PLUS: {
        "max_cards": 5,
        "max_budgets": 10,
        "max_recurring_services": 20,
        "max_categories": 25,
        "max_monthly_transactions": 500,
        "data_retention_months": 24,
    },
    UserTypeEnum.PRO: {
        "max_cards": -1,  # unlimited
        "max_budgets": -1,
        "max_recurring_services": -1,
        "max_categories": -1,
        "max_monthly_transactions": -1,
        "data_retention_months": -1,
    },
    UserTypeEnum.ADMIN: {
        "max_cards": -1,
        "max_budgets": -1,
        "max_recurring_services": -1,
        "max_categories": -1,
        "max_monthly_transactions": -1,
        "data_retention_months": -1,
    }
}

# Define permissions for each user type
_FREE_PERMISSIONS = [
    # Basic permissions
    Permission.VIEW_PROFILE,
    Permission.EDIT_PROFILE,
    
    # Transaction permissions (limited)
    Permission.VIEW_TRANSACTIONS,
    Permission.ADD_TRANSACTIONS,
    Permission.EDIT_TRANSACTIONS,
    
    # Budget permissions (limited)
    Permission.VIEW_BUDGETS,
    Permission.CREATE_BUDGETS,
    Permission.EDIT_BUDGETS,
    
    # Category permissions (limited)
    Permission.VIEW_CATEGORIES,
    Permission.CREATE_CATEGORIES,
    Permission.EDIT_CATEGORIES,
    
    # Card permissions (limited)
    Permission.VIEW_CARDS,
    Permission.ADD_CARDS,
    Permission.EDIT_CARDS,
    
    # Recurring service permissions (limited)
    Permission.VIEW_RECURRING_SERVICES,
    Permission.CREATE_RECURRING_SERVICES,
    Permission.EDIT_RECURRING_SERVICES,
    
    # Alert permissions (basic)
    Permission.VIEW_ALERTS,
    Permission.CREATE_ALERTS,
    
    # Statement permissions (basic)
    Permission.VIEW_STATEMENTS,
    Permission.UPLOAD_STATEMENTS,
]

_PLUS_PERMISSIONS = [
    # All free permissions
    *_FREE_PERMISSIONS,
    
    # Additional permissions
    Permission.DELETE_TRANSACTIONS,
    Permission.DELETE_BUDGETS,
    Permission.DELETE_CATEGORIES,
    Permission.DELETE_CARDS,
    Permission.DELETE_RECURRING_SERVICES,
    Permission.EDIT_ALERTS,
    Permission.DELETE_ALERTS,
    Permission.DELETE_STATEMENTS,
    Permission.EXPORT_DATA,
]

_PRO_PERMISSIONS = [
    # All plus permissions
    *_PLUS_PERMISSIONS,
    
    # Advanced features
    Permission.ADVANCED_REPORTS,
    Permission.BULK_OPERATIONS,
    Permission.API_ACCESS,
]

_ADMIN_PERMISSIONS = [
    # All pro permissions
    *_PRO_PERMISSIONS,
    
    # Admin permissions
    Permission.VIEW_ALL_USERS,
    Permission.EDIT_ALL_USERS,
    Permission.DELETE_ALL_USERS,
    Permission.VIEW_SYSTEM_METRICS,
    Permission.MANAGE_SYSTEM_SETTINGS,
]

USER_PERMISSIONS: Dict[UserTypeEnum, List[Permission]] = {
    UserTypeEnum.FREE: _FREE_PERMISSIONS,
    UserTypeEnum.PLUS: _PLUS_PERMISSIONS,
    UserTypeEnum.PRO: _PRO_PERMISSIONS,
    UserTypeEnum.ADMIN: _ADMIN_PERMISSIONS,
}

def has_permission(user_type: UserTypeEnum, permission: Permission) -> bool:
    """Check if a user type has a specific permission."""
    return permission in USER_PERMISSIONS.get(user_type, [])

def get_user_permissions(user_type: UserTypeEnum) -> List[Permission]:
    """Get all permissions for a user type."""
    return USER_PERMISSIONS.get(user_type, [])

def get_user_limits(user_type: UserTypeEnum) -> Dict[str, int]:
    """Get limits for a user type."""
    return USER_LIMITS.get(user_type, {})

def check_limit(user_type: UserTypeEnum, limit_name: str, current_count: int) -> bool:
    """Check if current count is within limits for user type."""
    limits = get_user_limits(user_type)
    max_limit = limits.get(limit_name, 0)
    
    # -1 means unlimited
    if max_limit == -1:
        return True
    
    return current_count < max_limit