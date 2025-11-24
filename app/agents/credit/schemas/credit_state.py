"""
Credit System State Schema
"""

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field


class CreditMessage(BaseModel):
    """Credit system message"""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: Optional[Dict[str, Any]] = None


class CreditState(TypedDict):
    """State for credit system graph - using TypedDict for performance"""

    messages: List[Dict[str, Any]]
    current_agent: str
    user_id: str
    user_role: str
    session_id: str
    credit_account_id: Optional[str]
    context: Dict[str, Any]
    last_update: str
    intent: Optional[str]
    risk_score: Optional[float]
    credit_limit: Optional[float]
    available_credit: Optional[float]
    payment_history: Optional[List[Dict[str, Any]]]
    pending_operations: Optional[List[Dict[str, Any]]]

