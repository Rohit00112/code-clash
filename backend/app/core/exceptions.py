"""Custom exception classes for the application"""

from typing import Optional, Dict, Any


class BaseAPIException(Exception):
    """Base exception for all API errors"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Authentication Errors
class AuthenticationError(BaseAPIException):
    """Base authentication error"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""
    def __init__(self):
        super().__init__("Invalid username or password")


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""
    def __init__(self):
        super().__init__("Token has expired")


class TokenInvalidError(AuthenticationError):
    """JWT token is invalid"""
    def __init__(self):
        super().__init__("Invalid token")


class AccountLockedError(AuthenticationError):
    """Account is locked due to failed login attempts"""
    def __init__(self, locked_until: str):
        super().__init__(
            f"Account is locked until {locked_until}",
            details={"locked_until": locked_until}
        )


# Authorization Errors
class AuthorizationError(BaseAPIException):
    """Insufficient permissions"""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


# Resource Errors
class ResourceNotFoundError(BaseAPIException):
    """Resource not found"""
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", status_code=404)


class ResourceAlreadyExistsError(BaseAPIException):
    """Resource already exists"""
    def __init__(self, resource: str):
        super().__init__(f"{resource} already exists", status_code=409)


# Validation Errors
class ValidationError(BaseAPIException):
    """Validation error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, details=details)


# Business Logic Errors
class BusinessLogicError(BaseAPIException):
    """Business logic error"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class SubmissionLimitExceededError(BusinessLogicError):
    """Submission limit exceeded"""
    def __init__(self):
        super().__init__("Submission limit exceeded for this question")


class EventNotActiveError(BusinessLogicError):
    """Event is not active"""
    def __init__(self):
        super().__init__("Event is not currently active")


class DuplicateUsernameError(BusinessLogicError):
    """Username already exists"""
    def __init__(self, username: str):
        super().__init__(f"Username '{username}' already exists")


# System Errors
class DatabaseError(BaseAPIException):
    """Database operation failed"""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status_code=500)


class CodeExecutionError(BaseAPIException):
    """Code execution failed"""
    def __init__(self, message: str = "Code execution failed"):
        super().__init__(message, status_code=500)


class FileSystemError(BaseAPIException):
    """File system operation failed"""
    def __init__(self, message: str = "File system operation failed"):
        super().__init__(message, status_code=500)


class ConcurrentModificationError(BaseAPIException):
    """Concurrent modification detected"""
    def __init__(self, message: str = "Resource was modified by another request"):
        super().__init__(message, status_code=409)


class RateLimitExceededError(BaseAPIException):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message, status_code=429)


class CircuitBreakerOpenError(BaseAPIException):
    """Circuit breaker is open"""
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, status_code=503)
