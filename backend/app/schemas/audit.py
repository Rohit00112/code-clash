"""Audit event response schemas."""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str] = None
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    ip_address: Optional[str]
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime]
