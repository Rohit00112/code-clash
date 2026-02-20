"""Admin routes - bulk operations and event management"""

from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app.core.database import get_db
from app.schemas.user import BulkUserImport, UserCredentials
from app.services.user_service import user_service
from app.services.challenge_loader import challenge_loader
from app.api.deps import get_current_admin_user
from app.models.user import User
from app.core.exceptions import ValidationError

router = APIRouter()


@router.post("/bulk-import", status_code=status.HTTP_201_CREATED)
def bulk_import_users(
    import_data: BulkUserImport,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Bulk import users with auto-generated passwords
    
    Args:
        import_data: Bulk import data
        current_user: Current admin user
        db: Database session
        
    Returns:
        Created users with credentials and errors
    """
    created_users, errors = user_service.bulk_import_users(db, import_data)
    
    return {
        "success": True,
        "created_count": len(created_users),
        "error_count": len(errors),
        "users": created_users,
        "errors": errors
    }


@router.delete("/delete-all-participants", status_code=status.HTTP_200_OK)
def delete_all_participants(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete all participant users (admin only)
    
    Args:
        current_user: Current admin user
        db: Database session
        
    Returns:
        Number of users deleted
    """
    count = user_service.delete_all_participants(db)
    
    return {
        "success": True,
        "message": f"Deleted {count} participants",
        "deleted_count": count
    }


@router.post("/reset-event", status_code=status.HTTP_200_OK)
def reset_event(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Reset entire event - delete all participants, submissions, drafts
    
    Args:
        current_user: Current admin user
        db: Database session
        
    Returns:
        Statistics of deleted items
    """
    stats = user_service.reset_event(db)
    
    return {
        "success": True,
        "message": "Event reset successfully",
        "deleted": stats
    }


@router.get("/submission-details")
def get_submission_details(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users with their best submission per question.
    Optimized: uses a single query instead of N*M individual queries.
    """
    from app.models.submission import Submission
    from sqlalchemy import func, and_

    participants = db.query(User).filter(User.role == "participant").all()
    questions = challenge_loader.get_available_questions()
    question_ids = [q["id"] for q in questions]

    # Single query: get the best submission (max score, latest date) per user per question
    # Subquery to find the max score per (user_id, question_id)
    best_score_sub = db.query(
        Submission.user_id,
        Submission.question_id,
        func.max(Submission.score).label("max_score")
    ).filter(
        Submission.status == "completed"
    ).group_by(
        Submission.user_id, Submission.question_id
    ).subquery()

    # Join to get the actual submission rows matching the max score
    # Pick the latest one if there are ties
    best_subs = db.query(Submission).join(
        best_score_sub,
        and_(
            Submission.user_id == best_score_sub.c.user_id,
            Submission.question_id == best_score_sub.c.question_id,
            Submission.score == best_score_sub.c.max_score,
            Submission.status == "completed"
        )
    ).order_by(Submission.submitted_at.desc()).all()

    # Build a lookup: (user_id, question_id) -> best submission
    # Since we ordered by submitted_at desc, first occurrence wins
    best_lookup = {}
    for sub in best_subs:
        key = (sub.user_id, sub.question_id)
        if key not in best_lookup:
            best_lookup[key] = sub

    result = []
    for user in participants:
        user_subs = {}
        for q_id in question_ids:
            best = best_lookup.get((user.id, q_id))
            if best:
                user_subs[q_id] = {
                    "id": best.id,
                    "code": best.code,
                    "language": best.language,
                    "score": best.score,
                    "submitted_at": best.submitted_at.isoformat() if best.submitted_at else None
                }
        result.append({
            "user_id": user.id,
            "username": user.username,
            "solutions": user_subs
        })

    return {"users": result}


@router.get("/statistics")
def get_statistics(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get platform statistics (admin only)
    
    Args:
        current_user: Current admin user
        db: Database session
        
    Returns:
        Platform statistics
    """
    from app.models.submission import Submission
    from app.models.draft import CodeDraft
    from sqlalchemy import func
    
    total_users = db.query(User).count()
    total_participants = db.query(User).filter(User.role == "participant").count()
    total_admins = db.query(User).filter(User.role == "admin").count()
    total_submissions = db.query(Submission).count()
    total_drafts = db.query(CodeDraft).count()
    completed = db.query(Submission).filter(Submission.status == "completed")
    avg_score = db.query(func.avg(Submission.score)).filter(
        Submission.status == "completed"
    ).scalar() or 0
    
    return {
        "total_users": total_users,
        "total_participants": total_participants,
        "active_participants": total_participants,
        "total_admins": total_admins,
        "total_submissions": total_submissions,
        "total_drafts": total_drafts,
        "average_score": round(float(avg_score), 1)
    }



@router.get("/export-results")
def export_results(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Export results to Excel
    
    Args:
        current_user: Current admin user
        db: Database session
        
    Returns:
        Excel file
    """
    from app.services.excel_service import excel_service
    from fastapi.responses import FileResponse
    
    filepath = excel_service.generate_results_report(db)
    
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@router.post("/export-credentials")
def export_credentials(
    users: List[dict],
    current_user: User = Depends(get_current_admin_user)
):
    """
    Export user credentials to Excel
    
    Args:
        users: List of user credentials
        current_user: Current admin user
        
    Returns:
        Excel file
    """
    from app.services.excel_service import excel_service
    from fastapi.responses import FileResponse
    
    filepath = excel_service.generate_credentials_export(users)
    
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"credentials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@router.post("/challenges/upload", status_code=status.HTTP_201_CREATED)
async def upload_challenge(
    pdf_file: UploadFile = File(...),
    testcase_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin_user)
):
    """Upload a new challenge (PDF + test case JSON)"""
    # Validate PDF
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise ValidationError("PDF file must have .pdf extension")

    # Read and validate test case JSON
    try:
        testcase_bytes = await testcase_file.read()
        testcase_data = json.loads(testcase_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Test case file must be valid JSON")

    # Validate JSON structure
    if "function_name" not in testcase_data:
        raise ValidationError("Test case JSON must have 'function_name' field")
    if "test_cases" not in testcase_data or not isinstance(testcase_data["test_cases"], list):
        raise ValidationError("Test case JSON must have 'test_cases' array")
    if len(testcase_data["test_cases"]) == 0:
        raise ValidationError("Test case JSON must have at least 1 test case")

    for i, tc in enumerate(testcase_data["test_cases"]):
        if "input" not in tc:
            raise ValidationError(f"Test case {i+1} missing 'input' field")
        if "output" not in tc:
            raise ValidationError(f"Test case {i+1} missing 'output' field")
        # Auto-assign id and is_sample if missing
        if "id" not in tc:
            tc["id"] = i + 1
        if "is_sample" not in tc:
            tc["is_sample"] = i < 2

    # Set title if provided
    if title:
        testcase_data["title"] = title

    # Get next question ID and save
    question_id = challenge_loader.get_next_question_id()
    pdf_bytes = await pdf_file.read()
    question = challenge_loader.save_question(question_id, pdf_bytes, testcase_data)

    return {
        "success": True,
        "message": f"Challenge {question_id} uploaded",
        "challenge": question
    }


@router.delete("/challenges/{question_id}")
def delete_challenge(
    question_id: str,
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a challenge (PDF + test case files)"""
    if not challenge_loader.validate_question_exists(question_id):
        raise ValidationError(f"Challenge {question_id} not found")

    challenge_loader.delete_question(question_id)

    return {
        "success": True,
        "message": f"Challenge {question_id} deleted"
    }
