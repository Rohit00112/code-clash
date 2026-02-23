from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import admin as admin_routes
from app.core.database import Base
from app.models.draft import CodeDraft
from app.models.submission import Submission
from app.models.user import User


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_delete_challenge_deletes_drafts_but_keeps_submissions(monkeypatch):
    db = _make_session()
    try:
        admin_user = User(username="admin", password_hash="hash", role="admin", is_active=True)
        participant = User(username="participant1", password_hash="hash", role="participant", is_active=True)
        db.add_all([admin_user, participant])
        db.commit()
        db.refresh(admin_user)
        db.refresh(participant)

        draft = CodeDraft(
            user_id=participant.id,
            question_id="question42",
            language="python",
            code="def solve(*args):\n    pass\n",
            version=1,
        )
        submission = Submission(
            idempotency_key="idem-question42",
            user_id=participant.id,
            question_id="question42",
            language="python",
            code="print('hello')",
            status="queued",
        )
        db.add_all([draft, submission])
        db.commit()

        calls = {"validated": 0, "deleted": 0}

        def fake_validate(question_id: str) -> bool:
            calls["validated"] += 1
            return question_id == "question42"

        def fake_delete(question_id: str) -> bool:
            if question_id == "question42":
                calls["deleted"] += 1
            return True

        audit_payload = {}

        def fake_log_event(*args, **kwargs):
            audit_payload.update(kwargs.get("metadata") or {})

        monkeypatch.setattr(admin_routes.challenge_loader, "validate_question_exists", fake_validate)
        monkeypatch.setattr(admin_routes.challenge_loader, "delete_question", fake_delete)
        monkeypatch.setattr(admin_routes.audit_service, "log_event", fake_log_event)

        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        response = admin_routes.delete_challenge(
            "question42",
            request=request,
            current_user=admin_user,
            db=db,
        )

        assert response["success"] is True
        assert response["deleted_drafts"] == 1
        assert calls["validated"] == 1
        assert calls["deleted"] == 1
        assert audit_payload["deleted_drafts"] == 1

        assert db.query(CodeDraft).filter(CodeDraft.question_id == "question42").count() == 0
        assert db.query(Submission).filter(Submission.question_id == "question42").count() == 1
    finally:
        db.close()
