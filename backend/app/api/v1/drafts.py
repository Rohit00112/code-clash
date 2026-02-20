"""Draft routes - auto-save functionality"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft import DraftResponse, DraftSaveRequest, DraftLoadRequest
from app.services.draft_service import draft_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/save", response_model=DraftResponse, status_code=status.HTTP_200_OK)
def save_draft(
    request: DraftSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save or update code draft (auto-save endpoint)
    
    Args:
        request: Draft save request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated draft
    """
    draft = draft_service.save_draft(
        db=db,
        user_id=current_user.id,
        question_id=request.question_id,
        language=request.language.value,
        code=request.code,
        current_version=request.current_version
    )
    
    return draft


@router.post("/load", response_model=DraftResponse)
def load_draft(
    request: DraftLoadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Load code draft or get default template
    
    Args:
        request: Draft load request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Draft or default template
    """
    draft = draft_service.load_draft(
        db=db,
        user_id=current_user.id,
        question_id=request.question_id,
        language=request.language.value
    )
    
    return draft


@router.get("/my-drafts", response_model=list)
def get_my_drafts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all drafts for current user
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of user's drafts
    """
    drafts = draft_service.get_user_drafts(db, current_user.id)
    return drafts


@router.delete("/{question_id}/{language}", status_code=status.HTTP_200_OK)
def delete_draft(
    question_id: str,
    language: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete specific draft
    
    Args:
        question_id: Question identifier
        language: Programming language
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    deleted = draft_service.delete_draft(
        db=db,
        user_id=current_user.id,
        question_id=question_id,
        language=language
    )
    
    if deleted:
        return {"success": True, "message": "Draft deleted successfully"}
    else:
        return {"success": False, "message": "Draft not found"}
