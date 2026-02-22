"""Audit service for sensitive admin events."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


class AuditService:
    """Persist immutable audit trail entries."""

    @staticmethod
    def log_event(
        db: Session,
        *,
        user_id: Optional[int],
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event


audit_service = AuditService()
