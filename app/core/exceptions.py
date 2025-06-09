"""
Custom exceptions for the application
"""

class BaseAppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class NotFoundError(BaseAppException):
    """Raised when a resource is not found"""
    pass


class ValidationError(BaseAppException):
    """Raised when validation fails"""
    pass


class AuthenticationError(BaseAppException):
    """Raised when authentication fails"""
    pass


class AuthorizationError(BaseAppException):
    """Raised when authorization fails"""
    pass


class BusinessLogicError(BaseAppException):
    """Raised when business logic constraints are violated"""
    pass


class ExternalServiceError(BaseAppException):
    """Raised when external service calls fail"""
    pass


class DatabaseError(BaseAppException):
    """Raised when database operations fail"""
    pass
