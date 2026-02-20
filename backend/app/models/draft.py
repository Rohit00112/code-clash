"""Code draft model for auto-save functionality"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CodeDraft(Base):
    """Code draft model - stores user's work in progress"""
    
    __tablename__ = "code_drafts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String(20), nullable=False)
    language = Column(String(20), nullable=False)
    code = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)  # For optimistic locking
    last_saved = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="drafts")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'question_id', 'language', name='uq_user_question_lang'),
        Index('idx_drafts_user_question', 'user_id', 'question_id'),
        CheckConstraint('length(code) <= 51200', name='chk_code_length'),
        CheckConstraint(
            "language IN ('python', 'java', 'c', 'cpp', 'javascript', 'csharp')",
            name='chk_language'
        ),
    )
    
    def __repr__(self):
        return f"<CodeDraft(id={self.id}, user_id={self.user_id}, question_id='{self.question_id}', language='{self.language}')>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "question_id": self.question_id,
            "language": self.language,
            "code": self.code,
            "version": self.version,
            "last_saved": self.last_saved.isoformat() if self.last_saved else None
        }
