"""Generic API response schemas"""

from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime


class APIResponse(BaseModel):
    """Generic API success response"""
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: str = datetime.utcnow().isoformat()


class ErrorResponse(BaseModel):
    """Generic API error response"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    path: Optional[str] = None
    timestamp: str = datetime.utcnow().isoformat()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: str
