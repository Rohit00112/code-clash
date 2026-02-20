"""Authentication routes"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.config import settings
from app.schemas.user import UserLogin, TokenResponse, UserResponse
from app.services.user_service import user_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    credentials: UserLogin,
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
    # Authenticate user
    user = user_service.authenticate_user(db, credentials.username, credentials.password)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(user)
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout endpoint - invalidate token (client-side)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    return {
        "success": True,
        "message": "Logged out successfully"
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
    current_user: User = Depends(get_current_user)
):
    """
    Refresh access token
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        New JWT token
    """
    # Create new access token
    access_token = create_access_token(
        data={"sub": str(current_user.id), "username": current_user.username, "role": current_user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(current_user)
    )
