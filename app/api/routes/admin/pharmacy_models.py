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

    # Account selection state (for returning users with registered accounts)
    registered_accounts_for_selection: list[dict[str, Any]] | None = None
    account_count: int | None = None

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = {"extra": "allow"}


# ============================================================
# INTERACTIVE MESSAGE MODELS
# ============================================================


class InteractiveButton(BaseModel):
    """WhatsApp interactive reply button."""

    id: str = Field(..., description="Button ID returned when clicked")
    titulo: str = Field(..., description="Button display text (max 20 chars)")


class InteractiveListItem(BaseModel):
    """WhatsApp interactive list item."""

    id: str = Field(..., description="Item ID returned when selected")
    titulo: str = Field(..., description="Item title (max 24 chars)")
    descripcion: str | None = Field(None, description="Item description (max 72 chars)")


class InteractiveResponseInput(BaseModel):
    """User response from interactive element (button click or list selection)."""

    type: str = Field(..., description="Response type: 'button_reply' or 'list_reply'")
    id: str = Field(..., description="Selected button/item ID")
    title: str = Field(..., description="Selected button/item title")


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
    """Schema for pharmacy test message request.

    Mirrors the original webhook behavior:
    - whatsapp_phone_number_id (DID) determines pharmacy/organization via bypass routing
    - phone_number is the simulated customer phone
    - pharmacy_id is optional (only for legacy/override scenarios)
    """

    whatsapp_phone_number_id: str = Field(..., description="Business phone (DID) - used for bypass routing to identify pharmacy/organization")
    phone_number: str = Field(..., description="Simulated customer phone number")
    message: str | None = Field(None, description="Test message to send (optional if interactive_response provided)")
    interactive_response: InteractiveResponseInput | None = Field(
        None, description="Interactive response (button click or list selection)"
    )
    session_id: str | None = Field(None, description="Existing session ID")
    pharmacy_id: str | None = Field(None, description="Optional pharmacy ID override (normally determined via bypass routing)")


class PharmacyTestResponse(BaseModel):
    """Schema for pharmacy test message response."""

    session_id: str = Field(..., description="Session ID")
    response: str = Field(..., description="Agent response")
    # Interactive message data
    response_type: str = Field(default="text", description="Response type: 'text', 'buttons', or 'list'")
    response_buttons: list[InteractiveButton] | None = Field(None, description="Reply buttons (max 3)")
    response_list_items: list[InteractiveListItem] | None = Field(None, description="List items (max 10)")
    # Execution metadata
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
