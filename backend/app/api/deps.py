"""API dependencies - authentication and authorization"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models.user import User
from app.services.user_service import user_service

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        
    Returns:
        Current user
        
    Raises:
        AuthenticationError: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    
    # Get user ID from token
    user_id: Optional[int] = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    
    # Get user from database
    user = user_service.get_user_by_id(db, int(user_id))
    if not user:
        raise AuthenticationError("User not found")
    
    # Check if user is active
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user
    """
    if not current_user.is_active:
        raise AuthenticationError("User account is disabled")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current admin user (authorization check)
    
    Args:
        current_user: Current user from token
        
    Returns:
        Admin user
        
    Raises:
        AuthorizationError: If user is not admin
    """
    if current_user.role != "admin":
        raise AuthorizationError("Admin access required")
    return current_user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    
    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session
        
    Returns:
        Current user or None
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = user_service.get_user_by_id(db, int(user_id))
        return user if user and user.is_active else None
    
    except Exception:
        return None
