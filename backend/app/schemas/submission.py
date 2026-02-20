"""Submission schemas"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.schemas.draft import LanguageEnum


class SubmissionCreate(BaseModel):
    """Create submission schema"""
    question_id: str = Field(..., pattern=r'^question[1-9][0-9]*$')
    language: LanguageEnum
    code: str = Field(..., min_length=1, max_length=51200)
    
    @field_validator('code')
    @classmethod
    def sanitize_code(cls, v):
        """Sanitize code input"""
        v = v.replace('\x00', '')
        lines = v.split('\n')
        if len(lines) > 1000:
            raise ValueError('Code exceeds 1000 lines')
        return v


class TestResultResponse(BaseModel):
    """Test result response schema"""
    id: int
    test_case_id: int
    passed: bool
    execution_time: Optional[float]
    memory_used: Optional[int]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class SubmissionResponse(BaseModel):
    """Submission response schema"""
    id: int
    user_id: int
    question_id: str
    language: str
    score: int
    max_score: int
    execution_time: Optional[float]
    memory_used: Optional[int]
    status: str
    submitted_at: Optional[datetime]
    completed_at: Optional[datetime]
    test_results: Optional[List[TestResultResponse]] = None
    
    class Config:
        from_attributes = True


class SubmissionListResponse(BaseModel):
    """Submission list response (without code) - for admin"""
    id: int
    question_id: str
    language: str
    score: int
    max_score: int
    status: str
    submitted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ParticipantSubmissionListResponse(BaseModel):
    """Participant's submissions - no score exposed"""
    id: int
    question_id: str
    language: str
    status: str
    submitted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TestRunRequest(BaseModel):
    """Test run request (sample test cases only)"""
    question_id: str = Field(..., pattern=r'^question[1-9][0-9]*$')
    language: LanguageEnum
    code: str = Field(..., min_length=1, max_length=51200)


class TestRunResponse(BaseModel):
    """Test run response - participant sees only their output"""
    output: str  # What user's code printed (stdout)
    error: Optional[str] = None  # Compilation/runtime error if any


class ParticipantSubmitResponse(BaseModel):
    """Submit response for participant - no scores exposed"""
    success: bool = True
    message: str = "Submission successful"
    output: str = ""  # User's code output from sample run

