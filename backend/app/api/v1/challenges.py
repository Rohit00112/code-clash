"""Challenge routes"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from typing import List

from app.schemas.challenge import ChallengeResponse, ChallengeDetailResponse
from app.services.challenge_loader import challenge_loader
from app.api.deps import get_current_user, get_current_admin_user
from app.models.user import User
from app.core.exceptions import ResourceNotFoundError

router = APIRouter()


@router.get("/", response_model=List[ChallengeResponse])
def get_challenges(
    current_user: User = Depends(get_current_user)
):
    """
    Get all available challenges
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of challenges
    """
    questions = challenge_loader.get_available_questions()
    
    return [
        ChallengeResponse(
            id=q["id"],
            number=q["number"],
            title=q["title"],
            function_name=q.get("function_name", "solution"),
            pdf_available=q["pdf_available"],
            total_test_cases=q["total_test_cases"],
            sample_test_cases=q["sample_test_cases"],
            max_score=q["max_score"]
        )
        for q in questions
    ]


@router.get("/{question_id}", response_model=ChallengeResponse)
def get_challenge(
    question_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get specific challenge
    
    Args:
        question_id: Question identifier
        current_user: Current authenticated user
        
    Returns:
        Challenge details
    """
    question = challenge_loader.get_question(question_id)
    
    if not question:
        raise ResourceNotFoundError(f"Challenge {question_id}")
    
    return ChallengeResponse(
        id=question["id"],
        number=question["number"],
        title=question["title"],
        function_name=question.get("function_name", "solution"),
        pdf_available=question["pdf_available"],
        total_test_cases=question["total_test_cases"],
        sample_test_cases=question["sample_test_cases"],
        max_score=question["max_score"]
    )


@router.get("/{question_id}/pdf")
def get_challenge_pdf(
    question_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Download challenge PDF
    
    Args:
        question_id: Question identifier
        current_user: Current authenticated user
        
    Returns:
        PDF file
    """
    pdf_path = challenge_loader.get_pdf_path(question_id)
    
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{question_id}.pdf"
    )


@router.get("/{question_id}/sample-tests")
def get_sample_test_cases(
    question_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get sample test cases for a challenge (for test run)
    
    Args:
        question_id: Question identifier
        current_user: Current authenticated user
        
    Returns:
        Sample test cases
    """
    test_cases = challenge_loader.get_sample_test_cases(question_id)
    
    return {
        "question_id": question_id,
        "test_cases": test_cases
    }


@router.get("/{question_id}/admin-detail", response_model=ChallengeDetailResponse)
def get_challenge_admin_detail(
    question_id: str,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get full challenge details including all test cases (admin only)
    
    Args:
        question_id: Question identifier
        current_user: Current admin user
        
    Returns:
        Full challenge details
    """
    question = challenge_loader.get_question(question_id)
    
    if not question:
        raise ResourceNotFoundError(f"Challenge {question_id}")
    
    test_data = challenge_loader.load_test_cases(question_id)
    
    return ChallengeDetailResponse(
        id=question["id"],
        number=question["number"],
        title=question["title"],
        pdf_path=question["pdf_path"],
        testcase_path=question["testcase_path"],
        function_name=test_data["function_name"],
        test_cases=test_data["test_cases"],
        total_test_cases=test_data["total_test_cases"],
        sample_test_cases=test_data["sample_test_cases"],
        hidden_test_cases=test_data["hidden_test_cases"],
        max_score=question["max_score"]
    )
