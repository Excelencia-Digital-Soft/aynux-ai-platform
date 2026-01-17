# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic models for Medical Admin API.
# ============================================================================
"""
Medical Models - Request/response schemas for medical appointments testing.

Provides Pydantic models for the medical appointments testing interface.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# API REQUEST/RESPONSE SCHEMAS
# ============================================================


class InstitutionResponse(BaseModel):
    """Schema for institution list response."""

    id: str = Field(..., description="Institution config ID")
    name: str = Field(..., description="Institution name")
    code: str = Field(..., description="WhatsApp phone number ID (DID)")
    institution_key: str = Field(..., description="Institution unique key")
    institution_type: str = Field(..., description="Institution type (medical)")
    active: bool = Field(True, description="Whether institution is active")


class MedicalTestRequest(BaseModel):
    """Schema for medical test message request.

    Mirrors the original webhook behavior:
    - whatsapp_phone_number_id (DID) determines institution via bypass routing
    - phone_number is the simulated customer phone
    """

    whatsapp_phone_number_id: str = Field(
        ...,
        description="Business phone (DID) - used for bypass routing to identify institution",
    )
    phone_number: str = Field(..., description="Simulated customer phone number")
    message: str | None = Field(None, description="Test message to send")
    session_id: str | None = Field(None, description="Existing session ID")


class MedicalTestResponse(BaseModel):
    """Schema for medical test message response."""

    session_id: str = Field(..., description="Session ID")
    response: str = Field(..., description="Agent response")
    response_type: str = Field(default="text", description="Response type: 'text', 'buttons', or 'list'")
    execution_steps: list[Any] | None = Field(None, description="Execution trace")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
