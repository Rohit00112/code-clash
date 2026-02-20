"""Challenge schemas"""

from pydantic import BaseModel
from typing import List, Optional, Any


class TestCaseResponse(BaseModel):
    """Test case response (sample only for participants)"""
    id: int
    input: Any
    expected_output: Any
    is_sample: bool


class ChallengeResponse(BaseModel):
    """Challenge response schema"""
    id: str
    number: int
    title: str
    function_name: str
    pdf_available: bool
    total_test_cases: int
    sample_test_cases: int
    max_score: int


class ChallengeDetailResponse(BaseModel):
    """Challenge detail response (for admin)"""
    id: str
    number: int
    title: str
    pdf_path: str
    testcase_path: str
    function_name: str
    test_cases: List[dict]
    total_test_cases: int
    sample_test_cases: int
    hidden_test_cases: int
    max_score: int


class LeaderboardEntry(BaseModel):
    """Leaderboard entry"""
    rank: int
    username: str
    total_score: int
    question_scores: dict
    avg_execution_time: Optional[float]
    submission_count: int


class LeaderboardResponse(BaseModel):
    """Leaderboard response"""
    rankings: List[LeaderboardEntry]
    total_participants: int
    updated_at: str
