# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic models for Pharmacy Admin API.
# ============================================================================
"""
Pharmacy Models - Session state and request/response schemas.

Provides Pydantic models for pharmacy test session management
and API request/response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============================================================
# SESSION STATE MODELS
# ============================================================


class SerializedMessage(BaseModel):
    """Serializable representation of LangChain messages."""

    role: str  # "human" or "ai"
    content: str
    timestamp: str | None = None


class PharmacySessionState(BaseModel):
    """Pydantic model for Redis session storage."""

    session_id: str
    organization_id: str
    pharmacy_id: str  # Pharmacy config ID (unique per pharmacy)
    customer_id: str  # WhatsApp phone number
    messages: list[SerializedMessage] = Field(default_factory=list)

    # Pharmacy configuration (CRITICAL for multi-turn)
    pharmacy_name: str | None = None
    pharmacy_phone: str | None = None

    # Core state fields (from PharmacyState)
    customer_identified: bool = False
    plex_customer_id: int | None = None
    plex_customer: dict[str, Any] | None = None
    has_debt: bool = False
    total_debt: float | None = None
    debt_data: dict[str, Any] | None = None
    debt_status: str | None = None
    debt_id: str | None = None  # CRITICAL: Required for confirmation flow
    awaiting_confirmation: bool = False
    confirmation_received: bool = False
    workflow_step: str | None = None
    is_complete: bool = False
    error_count: int = 0

    # Payment state
    mp_preference_id: str | None = None
    mp_init_point: str | None = None
    mp_payment_status: str | None = None
    mp_external_reference: str | None = None
    awaiting_payment: bool = False
    payment_amount: float | None = None
    is_partial_payment: bool = False

    # Registration state
    awaiting_registration_data: bool = False
    registration_step: str | None = None

    # Person resolution state (CRITICAL for multi-turn identification)
    identification_step: str | None = None
    plex_customer_to_confirm: dict[str, Any] | None = None
    name_mismatch_count: int = 0
    awaiting_own_or_other: bool = False
    validation_step: str | None = None

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = {"extra": "allow"}


# ============================================================
# API REQUEST/RESPONSE SCHEMAS
# ============================================================


class PharmacyResponse(BaseModel):
    """Schema for pharmacy list response."""

    id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Pharmacy name")
    code: str = Field(..., description="WhatsApp phone number")
    address: str | None = Field(None, description="Pharmacy address")
    phone: str | None = Field(None, description="Pharmacy phone")
    active: bool = Field(True, description="Whether pharmacy is active")


class PharmacyTestRequest(BaseModel):
    """Schema for pharmacy test message request."""

    pharmacy_id: str = Field(..., description="Pharmacy organization ID")
    message: str = Field(..., description="Test message to send")
    session_id: str | None = Field(None, description="Existing session ID")
    phone_number: str | None = Field(None, description="Simulated customer phone")


class PharmacyTestResponse(BaseModel):
    """Schema for pharmacy test message response."""

    session_id: str = Field(..., description="Session ID")
    response: str = Field(..., description="Agent response")
    execution_steps: list[Any] | None = Field(None, description="Execution trace")
    graph_state: dict[str, Any] | None = Field(None, description="Current graph state")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class SessionHistoryResponse(BaseModel):
    """Schema for session history response."""

    session_id: str
    messages: list[dict[str, Any]]
    created_at: str
    updated_at: str
    execution_steps: list[Any]
    graph_state: dict[str, Any]


class GraphDataResponse(BaseModel):
    """Schema for graph visualization data response."""

    session_id: str
    nodes: list[dict[str, str]]
    edges: list[dict[str, str]]
    current_node: str | None
    visited_nodes: list[str]
