"""Authentication routes"""

from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.config import settings
from app.schemas.user import (
    UserLogin,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest,
    LogoutRequest,
)
from app.services.user_service import user_service
from app.services.token_service import token_service
from app.services.rate_limiter import rate_limiter
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import RateLimitExceededError, AuthenticationError

router = APIRouter()


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login endpoint - authenticate user and return JWT token
    
    Args:
        credentials: Username and password
        db: Database session
        
    Returns:
        JWT token and user info
    """
    client_ip = request.client.host if request.client else "unknown"
    user_key = credentials.username.strip().lower()
    per_min_key = f"login:min:{client_ip}:{user_key}"
    per_hour_key = f"login:hour:{client_ip}:{user_key}"
    if not rate_limiter.allow(per_min_key, settings.LOGIN_RATE_LIMIT_PER_MINUTE, 60):
        raise RateLimitExceededError("Too many login attempts. Please wait a minute.")
    if not rate_limiter.allow(per_hour_key, settings.LOGIN_RATE_LIMIT_PER_HOUR, 3600):
        raise RateLimitExceededError("Too many login attempts. Please try again later.")

    # Authenticate user
    user = user_service.authenticate_user(db, credentials.username, credentials.password)
    access_token, refresh_token = token_service.issue_token_pair(db, user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(user)
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    body: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout endpoint - invalidate token (client-side)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    revoked = False
    if body and body.refresh_token:
        revoked = token_service.revoke_refresh_token(db, body.refresh_token)

    return {
        "success": True,
        "message": "Logged out successfully",
        "refresh_token_revoked": revoked
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User information
    """
    return UserResponse.from_orm(current_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    req: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Refresh access token
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        New JWT token
    """
    client_ip = request.client.host if request.client else "unknown"
    per_min_key = f"refresh:min:{client_ip}"
    per_hour_key = f"refresh:hour:{client_ip}"
    if not rate_limiter.allow(per_min_key, settings.RATE_LIMIT_PER_MINUTE, 60):
        raise RateLimitExceededError("Too many refresh attempts. Slow down.")
    if not rate_limiter.allow(per_hour_key, settings.RATE_LIMIT_PER_HOUR, 3600):
        raise RateLimitExceededError("Too many refresh attempts. Try later.")

    try:
        current_user, access_token, refresh_token_value = token_service.rotate_refresh_token(
            db, req.refresh_token
        )
    except AuthenticationError:
        raise
    except Exception:
        raise AuthenticationError("Unable to refresh session")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(current_user)
    )
