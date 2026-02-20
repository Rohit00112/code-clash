"""User management routes"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.user import UserCreate, UserResponse, BulkUserImport, UserCredentials
from app.services.user_service import user_service
from app.api.deps import get_current_user, get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User profile
    """
    return UserResponse.from_orm(current_user)


@router.get("/", response_model=List[UserResponse])
def get_all_users(
    role: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (admin only)
    
    Args:
        role: Optional role filter
        current_user: Current admin user
        db: Database session
        
    Returns:
        List of users
    """
    users = user_service.get_all_users(db, role)
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Create new user (admin only)
    
    Args:
        user_data: User creation data
        current_user: Current admin user
        db: Database session
        
    Returns:
        Created user
    """
    user = user_service.create_user(db, user_data)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete user (admin only)
    
    Args:
        user_id: User ID to delete
        current_user: Current admin user
        db: Database session
        
    Returns:
        Success message
    """
    user_service.delete_user(db, user_id)
    
    return {
        "success": True,
        "message": f"User {user_id} deleted successfully"
    }
