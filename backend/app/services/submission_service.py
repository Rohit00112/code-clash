"""Submission service - handles code submissions and scoring"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any
import secrets

from app.models.submission import Submission
from app.schemas.submission import SubmissionCreate
from app.services.code_executor import code_executor
from app.services.challenge_loader import challenge_loader
from app.core.exceptions import ResourceNotFoundError
import logging

logger = logging.getLogger(__name__)


class SubmissionService:
    """Service for handling submissions"""
    
    @staticmethod
    def test_run(
        db: Session,
        user_id: int,
        question_id: str,
        language: str,
        code: str
    ) -> Dict[str, Any]:
        """
        Test run code against sample test cases
        
        Args:
            db: Database session
            user_id: User ID
            question_id: Question ID
            language: Programming language
            code: Source code
            
        Returns:
            Test run results
        """
        # Validate question exists
        if not challenge_loader.validate_question_exists(question_id):
            raise ResourceNotFoundError(f"Question {question_id}")

        # For test run: execute once against first sample input for iterative feedback.
        test_data = challenge_loader.load_test_cases(question_id)
        function_name = test_data["function_name"]

        # Use first sample test case input so the function has args to work with
        sample_cases = challenge_loader.get_sample_test_cases(question_id)
        test_input = sample_cases[0].get("input") if sample_cases else []

        try:
            result = code_executor.run_once(
                code=code,
                language=language,
                function_name=function_name,
                test_input=test_input,
                user_id=user_id
            )
            return {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                "execution_time_ms": result.get("execution_time_ms", 0),
                "error_type": result.get("error_type"),
                "error_message": result.get("error_message"),
            }
        except Exception as e:
            logger.error(f"Test run error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "execution_time_ms": 0,
                "error_type": "runtime_error",
                "error_message": str(e),
            }
    
    @staticmethod
    def submit_code(
        db: Session,
        user_id: int,
        submission_data: SubmissionCreate
    ) -> Dict[str, Any]:
        """
        Enqueue code for async evaluation.
        
        Args:
            db: Database session
            user_id: User ID
            submission_data: Submission data
            
        Returns:
            Submission result
        """
        # Validate question exists
        if not challenge_loader.validate_question_exists(submission_data.question_id):
            raise ResourceNotFoundError(f"Question {submission_data.question_id}")
        
        # Generate idempotency key
        idempotency_key = secrets.token_urlsafe(32)
        
        # Create submission record
        submission = Submission(
            idempotency_key=idempotency_key,
            user_id=user_id,
            question_id=submission_data.question_id,
            language=submission_data.language.value,
            code=submission_data.code,
            status="queued",
            retry_count=0
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)

        logger.info("Submission %s queued by user %s", submission.id, user_id)
        return {
            "success": True,
            "submission_id": submission.id,
            "status": submission.status,
            "message": "Submission queued for evaluation",
        }
    
    @staticmethod
    def get_user_submissions(
        db: Session,
        user_id: int,
        question_id: str = None
    ) -> List[Submission]:
        """Get user's submissions"""
        query = db.query(Submission).filter(Submission.user_id == user_id)
        
        if question_id:
            query = query.filter(Submission.question_id == question_id)
        
        return query.order_by(Submission.submitted_at.desc()).all()
    
    @staticmethod
    def get_submission(db: Session, submission_id: int) -> Submission:
        """Get submission by ID"""
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        
        if not submission:
            raise ResourceNotFoundError("Submission")
        
        return submission
    
    @staticmethod
    def get_leaderboard(db: Session) -> List[Dict[str, Any]]:
        """
        Get leaderboard with rankings
        
        Args:
            db: Database session
            
        Returns:
            Leaderboard data
        """
        from app.models.user import User
        from sqlalchemy import func
        
        # Get best score per user per question
        subquery = db.query(
            Submission.user_id,
            Submission.question_id,
            func.max(Submission.score).label('best_score'),
            func.min(Submission.execution_time).label('best_time')
        ).filter(
            Submission.status == 'completed'
        ).group_by(
            Submission.user_id,
            Submission.question_id
        ).subquery()
        
        # Aggregate scores per user
        user_scores = db.query(
            User.id,
            User.username,
            func.sum(subquery.c.best_score).label('total_score'),
            func.avg(subquery.c.best_time).label('avg_time'),
            func.count(subquery.c.question_id).label('questions_solved')
        ).join(
            subquery,
            User.id == subquery.c.user_id
        ).filter(
            User.role == 'participant'
        ).group_by(
            User.id,
            User.username
        ).order_by(
            func.sum(subquery.c.best_score).desc(),
            func.avg(subquery.c.best_time).asc()
        ).all()
        
        # Format leaderboard
        leaderboard = []
        for rank, (user_id, username, total_score, avg_time, questions_solved) in enumerate(user_scores, 1):
            # Get question-wise scores
            question_scores = {}
            user_submissions = db.query(
                Submission.question_id,
                func.max(Submission.score).label('score')
            ).filter(
                Submission.user_id == user_id,
                Submission.status == 'completed'
            ).group_by(
                Submission.question_id
            ).all()
            
            for q_id, score in user_submissions:
                question_scores[q_id] = score
            
            leaderboard.append({
                "rank": rank,
                "username": username,
                "total_score": int(total_score or 0),
                "question_scores": question_scores,
                "avg_execution_time": round(float(avg_time or 0), 3),
                "questions_solved": questions_solved
            })
        
        return leaderboard


# Singleton instance
submission_service = SubmissionService()
