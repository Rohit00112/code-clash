"""Admin routes - bulk operations and event management"""

from fastapi import APIRouter, Depends, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app.core.database import get_db
from app.schemas.user import BulkUserImport
from app.schemas.challenge import ChallengeValidateRequest, ChallengeValidateResponse
from app.schemas.audit import AuditEventResponse
from app.services.user_service import user_service
from app.services.challenge_loader import challenge_loader
from app.services.testcase_validator import testcase_validator
from app.services.audit_service import audit_service
from app.api.deps import get_current_admin_user
from app.models.user import User
from app.models.audit import AuditEvent
from app.core.exceptions import ValidationError

router = APIRouter()


@router.post("/bulk-import", status_code=status.HTTP_201_CREATED)
def bulk_import_users(
    import_data: BulkUserImport,
    request: Request,
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
    audit_service.log_event(
        db,
        user_id=current_user.id,
        action="bulk_import_users",
        target_type="user",
        target_id="participant",
        ip_address=request.client.host if request.client else None,
        metadata={
            "requested": len(import_data.usernames),
            "created_count": len(created_users),
            "error_count": len(errors),
        },
    )
    
    return {
        "success": True,
        "created_count": len(created_users),
        "error_count": len(errors),
        "users": created_users,
        "errors": errors
    }


@router.delete("/delete-all-participants", status_code=status.HTTP_200_OK)
def delete_all_participants(
    request: Request,
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
    audit_service.log_event(
        db,
        user_id=current_user.id,
        action="delete_all_participants",
        target_type="user",
        target_id="participant",
        ip_address=request.client.host if request.client else None,
        metadata={"deleted_count": count},
    )
    
    return {
        "success": True,
        "message": f"Deleted {count} participants",
        "deleted_count": count
    }


@router.post("/reset-event", status_code=status.HTTP_200_OK)
def reset_event(
    request: Request,
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
    audit_service.log_event(
        db,
        user_id=current_user.id,
        action="reset_event",
        target_type="event",
        target_id="global",
        ip_address=request.client.host if request.client else None,
        metadata=stats,
    )
    
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


@router.post("/challenges/validate", response_model=ChallengeValidateResponse)
def validate_challenge_testcases(
    payload: ChallengeValidateRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """Validate challenge testcase JSON without persisting files."""
    normalized, warnings = testcase_validator.validate_and_normalize(payload.testcase_json)
    total = len(normalized["test_cases"])
    sample = sum(1 for tc in normalized["test_cases"] if tc.get("is_sample"))
    hidden = total - sample
    return ChallengeValidateResponse(
        valid=True,
        function_name=normalized["function_name"],
        total_test_cases=total,
        sample_test_cases=sample,
        hidden_test_cases=hidden,
        warnings=warnings,
    )


@router.get("/audit-events", response_model=List[AuditEventResponse])
def get_audit_events(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List recent audit trail entries."""
    query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if action:
        query = query.filter(AuditEvent.action == action)
    events = query.limit(max(1, min(limit, 500))).all()
    rows = []
    for ev in events:
        metadata = {}
        if ev.metadata_json:
            try:
                metadata = json.loads(ev.metadata_json)
            except Exception:
                metadata = {"raw": ev.metadata_json}
        rows.append(
            AuditEventResponse(
                id=ev.id,
                user_id=ev.user_id,
                username=ev.user.username if ev.user else None,
                action=ev.action,
                target_type=ev.target_type,
                target_id=ev.target_id,
                ip_address=ev.ip_address,
                metadata=metadata,
                created_at=ev.created_at,
            )
        )
    return rows


@router.post("/challenges/upload", status_code=status.HTTP_201_CREATED)
async def upload_challenge(
    request: Request,
    pdf_file: UploadFile = File(...),
    testcase_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Upload a new challenge (PDF + test case JSON)"""
    # Validate PDF
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise ValidationError("PDF file must have .pdf extension")
    if not testcase_file.filename.lower().endswith('.json'):
        raise ValidationError("Test case file must have .json extension")

    # Read and validate test case JSON
    try:
        testcase_bytes = await testcase_file.read()
        testcase_data = json.loads(testcase_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Test case file must be valid JSON")

    testcase_data, warnings = testcase_validator.validate_and_normalize(testcase_data)

    # Set title if provided
    if title:
        testcase_data["title"] = title

    # Get next question ID and save
    question_id = challenge_loader.get_next_question_id()
    pdf_bytes = await pdf_file.read()
    question = challenge_loader.save_question(question_id, pdf_bytes, testcase_data)
    if request:
        audit_service.log_event(
            db,
            user_id=current_user.id,
            action="upload_challenge",
            target_type="challenge",
            target_id=question_id,
            ip_address=request.client.host if request.client else None,
            metadata={
                "title": testcase_data.get("title"),
                "total_test_cases": len(testcase_data.get("test_cases", [])),
                "warnings": warnings,
            },
        )

    return {
        "success": True,
        "message": f"Challenge {question_id} uploaded",
        "challenge": question,
        "warnings": warnings,
    }


@router.delete("/challenges/{question_id}")
def delete_challenge(
    question_id: str,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete a challenge (PDF + test case files)"""
    if not challenge_loader.validate_question_exists(question_id):
        raise ValidationError(f"Challenge {question_id} not found")

    challenge_loader.delete_question(question_id)
    audit_service.log_event(
        db,
        user_id=current_user.id,
        action="delete_challenge",
        target_type="challenge",
        target_id=question_id,
        ip_address=request.client.host if request.client else None,
        metadata={},
    )

    return {
        "success": True,
        "message": f"Challenge {question_id} deleted"
    }
