"""Submission and test result models"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, Index, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Submission(Base):
    """Submission model - stores code submissions"""
    
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String(20), nullable=False)
    language = Column(String(20), nullable=False)
    code = Column(Text, nullable=False)
    score = Column(Integer, default=0)
    max_score = Column(Integer, default=100)
    execution_time = Column(Float)
    memory_used = Column(Integer)
    status = Column(String(20), default="pending", nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="submissions")
    test_results = relationship("TestResult", back_populates="submission", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_submissions_user', 'user_id'),
        Index('idx_submissions_question', 'question_id'),
        Index('idx_submissions_status', 'status'),
        Index('idx_submissions_submitted_at', 'submitted_at'),
        CheckConstraint('score >= 0 AND score <= 100', name='chk_score_range'),
        CheckConstraint('execution_time >= 0', name='chk_execution_time'),
        CheckConstraint('memory_used >= 0', name='chk_memory_used'),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'timeout')",
            name='chk_status'
        ),
    )
    
    def __repr__(self):
        return f"<Submission(id={self.id}, user_id={self.user_id}, question_id='{self.question_id}', score={self.score})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "question_id": self.question_id,
            "language": self.language,
            "score": self.score,
            "max_score": self.max_score,
            "execution_time": self.execution_time,
            "memory_used": self.memory_used,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TestResult(Base):
    """Test result model - stores individual test case results"""
    
    __tablename__ = "test_results"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(Integer, nullable=False)
    passed = Column(Boolean, nullable=False)
    execution_time = Column(Float)
    memory_used = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    submission = relationship("Submission", back_populates="test_results")
    
    __table_args__ = (
        Index('idx_test_results_submission', 'submission_id'),
    )
    
    def __repr__(self):
        return f"<TestResult(id={self.id}, submission_id={self.submission_id}, passed={self.passed})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "submission_id": self.submission_id,
            "test_case_id": self.test_case_id,
            "passed": self.passed,
            "execution_time": self.execution_time,
            "memory_used": self.memory_used,
            "error_message": self.error_message
        }
