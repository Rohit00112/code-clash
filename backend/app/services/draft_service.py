"""Draft service - handles code auto-save with optimistic locking"""

from sqlalchemy.orm import Session
from sqlalchemy import update
from typing import Optional
from datetime import datetime
from app.models.draft import CodeDraft
from app.schemas.draft import DraftResponse
from app.core.exceptions import (
    ConcurrentModificationError,
    ValidationError
)
from app.services.challenge_loader import challenge_loader
import logging

logger = logging.getLogger(__name__)


class DraftService:
    """Service for managing code drafts"""
    
    @staticmethod
    def get_default_template(language: str, function_name: str = "solution") -> str:
        """
        Get default code template for language
        
        Args:
            language: Programming language
            
        Returns:
            Default code template
        """
        templates = {
            "python": f"def {function_name}(*args):\n    # Add parameters as per problem statement\n    pass\n",
            "java": (
                "public class Solution {\n"
                f"    public static Object {function_name}(Object input) {{\n"
                "        // Add parameters as per problem statement\n"
                "        return null;\n"
                "    }\n\n"
                "    public static void main(String[] args) {\n"
                "        // Optional local testing entrypoint\n"
                "    }\n"
                "}\n"
            ),
            "cpp": (
                "#include <bits/stdc++.h>\n"
                "using namespace std;\n\n"
                "// Update signature and return type based on problem statement.\n"
                "template <typename... Args>\n"
                f"int {function_name}(Args... args) {{\n"
                "    return 0;\n"
                "}\n\n"
                "int main() {\n"
                "    // Optional local testing entrypoint\n"
                "    return 0;\n"
                "}\n"
            ),
            "c": (
                "#include <stdio.h>\n\n"
                "// Update signature and implementation based on problem statement.\n"
                f"int {function_name}(void) {{\n"
                "    return 0;\n"
                "}\n\n"
                "int main(void) {\n"
                "    // Optional local testing entrypoint\n"
                "    return 0;\n"
                "}\n"
            ),
            "javascript": f"function {function_name}(...args) {{\n    // Add parameters as per problem statement\n}}\n",
            "csharp": (
                "using System;\n\n"
                "class Solution\n"
                "{\n"
                f"    public static object {function_name}(object input)\n"
                "    {\n"
                "        // Add parameters as per problem statement\n"
                "        return null;\n"
                "    }\n\n"
                "    static void Main()\n"
                "    {\n"
                "        // Optional local testing entrypoint\n"
                "    }\n"
                "}\n"
            )
        }
        return templates.get(language, "// Your code here\n")
    
    @staticmethod
    def save_draft(
        db: Session,
        user_id: int,
        question_id: str,
        language: str,
        code: str,
        current_version: Optional[int] = None
    ) -> DraftResponse:
        """
        Save or update draft with optimistic locking
        
        Args:
            db: Database session
            user_id: User ID
            question_id: Question ID
            language: Programming language
            code: Code content
            current_version: Current version for optimistic locking
            
        Returns:
            Updated draft
        """
        try:
            # Check if draft exists
            existing_draft = db.query(CodeDraft).filter(
                CodeDraft.user_id == user_id,
                CodeDraft.question_id == question_id,
                CodeDraft.language == language
            ).first()
            
            if existing_draft:
                # Update existing draft with optimistic locking
                if current_version is not None and existing_draft.version != current_version:
                    raise ConcurrentModificationError(
                        "Draft was modified by another request. Please refresh and try again."
                    )
                
                # Update using SQL to ensure atomicity
                result = db.execute(
                    update(CodeDraft)
                    .where(
                        CodeDraft.id == existing_draft.id,
                        CodeDraft.version == existing_draft.version
                    )
                    .values(
                        code=code,
                        version=existing_draft.version + 1,
                        last_saved=datetime.utcnow()
                    )
                )
                
                if result.rowcount == 0:
                    raise ConcurrentModificationError(
                        "Draft was modified by another request. Please refresh and try again."
                    )
                
                db.commit()
                
                # Refresh to get updated values
                db.refresh(existing_draft)
                
                logger.info(f"Updated draft for user {user_id}, question {question_id}, language {language}")
                return DraftResponse.from_orm(existing_draft)
            
            else:
                # Create new draft
                new_draft = CodeDraft(
                    user_id=user_id,
                    question_id=question_id,
                    language=language,
                    code=code,
                    version=1
                )
                db.add(new_draft)
                db.commit()
                db.refresh(new_draft)
                
                logger.info(f"Created draft for user {user_id}, question {question_id}, language {language}")
                return DraftResponse.from_orm(new_draft)
        
        except ConcurrentModificationError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving draft: {e}")
            raise ValidationError(f"Failed to save draft: {str(e)}")
    
    @staticmethod
    def load_draft(
        db: Session,
        user_id: int,
        question_id: str,
        language: str
    ) -> DraftResponse:
        """
        Load draft or return default template
        
        Args:
            db: Database session
            user_id: User ID
            question_id: Question ID
            language: Programming language
            
        Returns:
            Draft or default template
        """
        draft = db.query(CodeDraft).filter(
            CodeDraft.user_id == user_id,
            CodeDraft.question_id == question_id,
            CodeDraft.language == language
        ).first()
        
        if draft:
            return DraftResponse.from_orm(draft)
        
        # Return default template with correct function name for this question
        function_name = "solution"
        try:
            test_data = challenge_loader.load_test_cases(question_id)
            function_name = test_data.get("function_name", "solution")
        except Exception:
            pass
        return DraftResponse(
            id=0,
            user_id=user_id,
            question_id=question_id,
            language=language,
            code=DraftService.get_default_template(language, function_name),
            version=0,
            last_saved=None
        )
    
    @staticmethod
    def delete_draft(
        db: Session,
        user_id: int,
        question_id: str,
        language: str
    ) -> bool:
        """
        Delete draft
        
        Args:
            db: Database session
            user_id: User ID
            question_id: Question ID
            language: Programming language
            
        Returns:
            True if deleted
        """
        draft = db.query(CodeDraft).filter(
            CodeDraft.user_id == user_id,
            CodeDraft.question_id == question_id,
            CodeDraft.language == language
        ).first()
        
        if draft:
            db.delete(draft)
            db.commit()
            logger.info(f"Deleted draft for user {user_id}, question {question_id}, language {language}")
            return True
        
        return False
    
    @staticmethod
    def get_user_drafts(db: Session, user_id: int) -> list:
        """
        Get all drafts for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of drafts
        """
        drafts = db.query(CodeDraft).filter(
            CodeDraft.user_id == user_id
        ).all()
        
        return [DraftResponse.from_orm(draft) for draft in drafts]


# Singleton instance
draft_service = DraftService()
