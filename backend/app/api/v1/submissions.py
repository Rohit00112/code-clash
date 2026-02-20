"""Submission routes - code submission and testing"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    TestRunRequest,
    TestRunResponse,
    SubmissionListResponse,
    ParticipantSubmissionListResponse,
    ParticipantSubmitResponse
)
from app.api.deps import get_current_user, get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.post("/test-run", response_model=TestRunResponse)
def test_run(
    request: TestRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test run code against sample test cases
    
    Args:
        request: Test run request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Test run results
    """
    from app.services.submission_service import submission_service
    
    results = submission_service.test_run(
        db=db,
        user_id=current_user.id,
        question_id=request.question_id,
        language=request.language.value,
        code=request.code
    )
    
    return TestRunResponse(
        output=results.get("output", ""),
        error=results.get("error")
    )


@router.post("/submit", response_model=ParticipantSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_code(
    submission: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit code for evaluation
    
    Args:
        submission: Submission data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Submission result
    """
    from app.services.submission_service import submission_service
    
    result = submission_service.submit_code(
        db=db,
        user_id=current_user.id,
        submission_data=submission
    )
    
    return result


@router.get("/my-submissions", response_model=List[ParticipantSubmissionListResponse])
def get_my_submissions(
    question_id: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's submissions (no scores - participant view)
    """
    from app.models.submission import Submission
    
    query = db.query(Submission).filter(Submission.user_id == current_user.id)
    
    if question_id:
        query = query.filter(Submission.question_id == question_id)
    
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    
    return [ParticipantSubmissionListResponse.from_orm(sub) for sub in submissions]


@router.get("/leaderboard")
def get_leaderboard(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get leaderboard (admin only)"""
    from app.services.submission_service import submission_service
    leaderboard = submission_service.get_leaderboard(db)
    return {
        "rankings": leaderboard,
        "total_participants": len(leaderboard),
        "updated_at": datetime.utcnow().isoformat()
    }


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific submission details
    
    Args:
        submission_id: Submission ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Submission details
    """
    from app.models.submission import Submission
    from app.core.exceptions import ResourceNotFoundError, AuthorizationError
    
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    
    if not submission:
        raise ResourceNotFoundError("Submission")
    
    # Check authorization (user can only see own submissions, admin can see all)
    if submission.user_id != current_user.id and current_user.role != "admin":
        raise AuthorizationError("You can only view your own submissions")
    
    return SubmissionResponse.from_orm(submission)


@router.get("/")
def get_all_submissions(
    question_id: str = None,
    user_id: int = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all submissions (admin only)
    
    Args:
        question_id: Optional question filter
        user_id: Optional user filter
        current_user: Current admin user
        db: Database session
        
    Returns:
        List of all submissions
    """
    from app.models.submission import Submission
    from sqlalchemy.orm import joinedload
    
    query = db.query(Submission).options(joinedload(Submission.user))
    
    if question_id:
        query = query.filter(Submission.question_id == question_id)
    
    if user_id:
        query = query.filter(Submission.user_id == user_id)
    
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    result = []
    for sub in submissions:
        d = SubmissionResponse.from_orm(sub).model_dump()
        d['username'] = sub.user.username if sub.user else str(sub.user_id)
        result.append(d)
    return result


@router.delete("/{submission_id}", status_code=status.HTTP_200_OK)
def delete_submission(
    submission_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a submission (admin only)"""
    from app.models.submission import Submission
    from app.core.exceptions import ResourceNotFoundError
    
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise ResourceNotFoundError("Submission")
    db.delete(submission)
    db.commit()
    return {"success": True, "message": "Submission deleted"}
