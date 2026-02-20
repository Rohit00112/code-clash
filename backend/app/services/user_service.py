"""User service - handles user management and authentication"""

from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserCredentials, BulkUserImport
from app.core.security import get_password_hash, verify_password, generate_password
from app.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    DuplicateUsernameError,
    ResourceNotFoundError
)
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management"""
    
    LOCKOUT_DURATION_MINUTES = 15
    MAX_FAILED_ATTEMPTS = 5
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> UserResponse:
        """
        Create new user
        
        Args:
            db: Database session
            user_data: User creation data
            
        Returns:
            Created user
        """
        # Check if username exists
        existing = db.query(User).filter(User.username == user_data.username).first()
        if existing:
            raise DuplicateUsernameError(user_data.username)
        
        # Create user
        user = User(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role.value
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Created user: {user.username} (role: {user.role})")
        return UserResponse.from_orm(user)
    
    @staticmethod
    def bulk_import_users(
        db: Session,
        import_data: BulkUserImport
    ) -> Tuple[List[UserCredentials], List[str]]:
        """
        Bulk import users with auto-generated passwords
        
        Args:
            db: Database session
            import_data: Bulk import data
            
        Returns:
            Tuple of (created users with credentials, errors)
        """
        created_users = []
        errors = []
        
        for username in import_data.usernames:
            try:
                # Check if user exists
                existing = db.query(User).filter(User.username == username).first()
                if existing:
                    errors.append(f"Username '{username}' already exists")
                    continue
                
                # Generate password
                password = generate_password(username) if import_data.auto_generate_passwords else f"{username}@123"
                
                # Create user
                user = User(
                    username=username,
                    password_hash=get_password_hash(password),
                    role="participant"
                )
                
                db.add(user)
                db.flush()  # Flush to get ID but don't commit yet
                
                created_users.append(UserCredentials(
                    username=username,
                    password=password,
                    role="participant"
                ))
                
                logger.info(f"Bulk imported user: {username}")
            
            except Exception as e:
                errors.append(f"Error creating user '{username}': {str(e)}")
                logger.error(f"Error in bulk import for {username}: {e}")
        
        # Commit all at once
        if created_users:
            db.commit()
        
        return created_users, errors
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User:
        """
        Authenticate user with account lockout protection
        
        Args:
            db: Database session
            username: Username
            password: Password
            
        Returns:
            Authenticated user
        """
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise InvalidCredentialsError()
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise AccountLockedError(user.locked_until.isoformat())
        
        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account if max attempts reached
            if user.failed_login_attempts >= UserService.MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=UserService.LOCKOUT_DURATION_MINUTES
                )
                db.commit()
                logger.warning(f"Account locked for user: {username}")
                raise AccountLockedError(user.locked_until.isoformat())
            
            db.commit()
            raise InvalidCredentialsError()
        
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"User authenticated: {username}")
        return user
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_all_users(db: Session, role: Optional[str] = None) -> List[UserResponse]:
        """
        Get all users, optionally filtered by role
        
        Args:
            db: Database session
            role: Optional role filter
            
        Returns:
            List of users
        """
        query = db.query(User)
        
        if role:
            query = query.filter(User.role == role)
        
        users = query.all()
        return [UserResponse.from_orm(user) for user in users]
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """
        Delete user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if deleted
        """
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ResourceNotFoundError("User")
        
        # Don't allow deleting admin users
        if user.role == "admin":
            raise ValueError("Cannot delete admin user")
        
        db.delete(user)
        db.commit()
        
        logger.info(f"Deleted user: {user.username}")
        return True
    
    @staticmethod
    def delete_all_participants(db: Session) -> int:
        """
        Delete all participant users
        
        Args:
            db: Database session
            
        Returns:
            Number of users deleted
        """
        count = db.query(User).filter(User.role == "participant").delete()
        db.commit()
        
        logger.info(f"Deleted {count} participant users")
        return count
    
    @staticmethod
    def reset_event(db: Session) -> dict:
        """
        Reset entire event - delete all participants, submissions, drafts
        
        Args:
            db: Database session
            
        Returns:
            Statistics of deleted items
        """
        from app.models.submission import Submission
        from app.models.draft import CodeDraft
        
        # Count before deletion
        participant_count = db.query(User).filter(User.role == "participant").count()
        submission_count = db.query(Submission).count()
        draft_count = db.query(CodeDraft).count()
        
        # Delete all (cascade will handle related records)
        db.query(User).filter(User.role == "participant").delete()
        db.commit()
        
        logger.info(f"Event reset: {participant_count} participants, {submission_count} submissions, {draft_count} drafts deleted")
        
        return {
            "participants": participant_count,
            "submissions": submission_count,
            "drafts": draft_count
        }


# Singleton instance
user_service = UserService()
