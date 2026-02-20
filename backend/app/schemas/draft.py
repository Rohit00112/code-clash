"""Code draft schemas"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class LanguageEnum(str, Enum):
    """Supported programming languages"""
    PYTHON = "python"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    JAVASCRIPT = "javascript"
    CSHARP = "csharp"


class DraftCreate(BaseModel):
    """Create draft schema"""
    question_id: str = Field(..., pattern=r'^question[1-9][0-9]*$')
    language: LanguageEnum
    code: str = Field(..., min_length=1, max_length=51200)
    
    @field_validator('code')
    @classmethod
    def sanitize_code(cls, v):
        """Sanitize code input"""
        # Remove null bytes
        v = v.replace('\x00', '')
        
        # Check line count
        lines = v.split('\n')
        if len(lines) > 1000:
            raise ValueError('Code exceeds 1000 lines')
        
        return v


class DraftUpdate(BaseModel):
    """Update draft schema"""
    code: str = Field(..., min_length=1, max_length=51200)
    version: int = Field(..., ge=1)  # For optimistic locking
    
    @field_validator('code')
    @classmethod
    def sanitize_code(cls, v):
        """Sanitize code input"""
        v = v.replace('\x00', '')
        lines = v.split('\n')
        if len(lines) > 1000:
            raise ValueError('Code exceeds 1000 lines')
        return v


class DraftResponse(BaseModel):
    """Draft response schema"""
    id: int
    user_id: int
    question_id: str
    language: str
    code: str
    version: int
    last_saved: Optional[datetime]
    
    class Config:
        from_attributes = True


class DraftSaveRequest(BaseModel):
    """Auto-save draft request"""
    question_id: str = Field(..., pattern=r'^question[1-9][0-9]*$')
    language: LanguageEnum
    code: str = Field(..., max_length=51200)
    current_version: Optional[int] = None


class DraftLoadRequest(BaseModel):
    """Load draft request"""
    question_id: str = Field(..., pattern=r'^question[1-9][0-9]*$')
    language: LanguageEnum

