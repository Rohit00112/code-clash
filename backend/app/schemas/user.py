"""User schemas"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    PARTICIPANT = "participant"


class UserLogin(BaseModel):
    """User login schema"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=3)


class UserCreate(BaseModel):
    """User creation schema"""
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.PARTICIPANT
    
    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        """Validate username is alphanumeric"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (with _ or - allowed)')
        return v.lower()


class BulkUserImport(BaseModel):
    """Bulk user import schema"""
    usernames: List[str] = Field(..., min_length=1, max_length=100)
    auto_generate_passwords: bool = True
    
    @field_validator('usernames', mode='before')
    @classmethod
    def validate_usernames(cls, v):
        """Validate and clean usernames"""
        cleaned = []
        for username in v:
            username = username.strip().lower()
            if len(username) < 3:
                raise ValueError(f'Username "{username}" is too short (min 3 characters)')
            if len(username) > 50:
                raise ValueError(f'Username "{username}" is too long (max 50 characters)')
            if not username.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f'Username "{username}" contains invalid characters')
            cleaned.append(username)
        
        # Check for duplicates
        if len(cleaned) != len(set(cleaned)):
            raise ValueError('Duplicate usernames found in list')
        
        return cleaned


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserCredentials(BaseModel):
    """User credentials for export"""
    username: str
    password: str
    role: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
