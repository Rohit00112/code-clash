"""Background worker for queued submission evaluation."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.models.submission import Submission, TestResult
from app.services.challenge_loader import challenge_loader
from app.services.code_executor import code_executor

logger = logging.getLogger(__name__)


class SubmissionWorker:
    """DB-backed submission queue worker."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._heartbeat: float = 0.0
        self._processed_count: int = 0
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="submission-worker", daemon=True)
        self._thread.start()
        logger.info("Submission worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Submission worker stopped")

    def status(self) -> dict:
        return {
            "running": self.is_running(),
            "last_heartbeat": self._heartbeat,
            "processed_count": self._processed_count,
        }

    def queue_depth(self, db: Session) -> int:
        return db.query(Submission).filter(Submission.status == "queued").count()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = 0
            for _ in range(max(1, settings.WORKER_BATCH_SIZE)):
                did_work = self.process_next_submission()
                if did_work:
                    processed += 1
                else:
                    break
            self._heartbeat = time.time()
            if processed == 0:
                time.sleep(max(0.1, settings.WORKER_POLL_INTERVAL_SECONDS))

    def process_next_submission(self) -> bool:
        db = SessionLocal()
        try:
            base_query = (
                db.query(Submission)
                .filter(Submission.status == "queued")
                .order_by(Submission.submitted_at.asc())
            )
            try:
                submission = base_query.with_for_update(skip_locked=True).first()
            except Exception:
                submission = base_query.first()
            if not submission:
                return False

            submission.status = "running"
            submission.started_at = datetime.utcnow()
            db.commit()
            db.refresh(submission)

            try:
                self._evaluate_submission(db, submission)
            except Exception as exc:
                logger.exception("Submission %s processing failed: %s", submission.id, exc)
                db.rollback()
                db.refresh(submission)
                if submission.retry_count < settings.WORKER_MAX_RETRIES:
                    submission.retry_count += 1
                    submission.status = "queued"
                    submission.error_type = "worker_retry"
                    submission.error_message = str(exc)
                else:
                    submission.status = "failed"
                    submission.error_type = "worker_failure"
                    submission.error_message = str(exc)
                    submission.completed_at = datetime.utcnow()
                db.commit()
            finally:
                with self._lock:
                    self._processed_count += 1

            return True
        finally:
            db.close()

    def _evaluate_submission(self, db: Session, submission: Submission) -> None:
        test_cases = challenge_loader.get_all_test_cases(submission.question_id)
        test_data = challenge_loader.load_test_cases(submission.question_id)
        function_name = test_data["function_name"]

        results = code_executor.execute_code(
            code=submission.code,
            language=submission.language,
            test_cases=test_cases,
            function_name=function_name,
            user_id=submission.user_id,
        )

        passed = results["passed"]
        total = results["total"]
        score = int((passed / total) * 100) if total > 0 else 0

        submission.score = score
        submission.max_score = 100
        submission.execution_time = results["total_execution_time"]
        submission.error_type = results.get("error_type")
        submission.error_message = results.get("error_message")
        submission.completed_at = datetime.utcnow()

        # Final status.
        if results.get("error_type") == "time_limit_exceeded" and passed == 0:
            submission.status = "timeout"
        elif results.get("error_type") in {"compile_error", "runtime_error"} and passed == 0:
            submission.status = "failed"
        else:
            submission.status = "completed"

        # Replace prior test results on re-process.
        db.query(TestResult).filter(TestResult.submission_id == submission.id).delete()
        for test_result in results["test_results"]:
            db.add(
                TestResult(
                    submission_id=submission.id,
                    test_case_id=test_result["test_case_id"],
                    passed=test_result["passed"],
                    execution_time=test_result.get("execution_time"),
                    error_message=test_result.get("error"),
                )
            )

        db.commit()


submission_worker = SubmissionWorker()
