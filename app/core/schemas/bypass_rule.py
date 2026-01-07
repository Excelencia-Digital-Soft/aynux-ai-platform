"""
Bypass Rule Schemas.

Pydantic schemas for bypass routing rule API operations.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class BypassRuleCreate(BaseModel):
    """Schema for creating a bypass rule."""

    rule_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name for the rule",
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Description of what this rule does",
    )
    rule_type: Literal["phone_number", "phone_number_list", "whatsapp_phone_number_id"] = Field(
        ...,
        description="Type of matching rule",
    )
    pattern: str | None = Field(
        None,
        max_length=100,
        description="Pattern for phone_number type (e.g., '549264*' for San Juan)",
    )
    phone_numbers: list[str] | None = Field(
        None,
        description="List of phone numbers for phone_number_list type",
    )
    phone_number_id: str | None = Field(
        None,
        max_length=100,
        description="WhatsApp Business phone number ID for whatsapp_phone_number_id type",
    )
    target_agent: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Agent key to route to (e.g., 'pharmacy_operations_agent')",
    )
    target_domain: str | None = Field(
        None,
        max_length=50,
        description="Optional domain override (uses tenant default_domain if not set)",
    )
    pharmacy_id: str | None = Field(
        None,
        max_length=36,
        description="Pharmacy ID to link this rule to (required when target_domain='pharmacy')",
    )
    priority: int = Field(
        default=0,
        ge=-100,
        le=100,
        description="Priority for rule evaluation (higher = evaluated first)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this rule is active",
    )
    isolated_history: bool = Field(
        default=False,
        description="When true, creates isolated conversation history separate from other agents",
    )

    @field_validator("pharmacy_id")
    @classmethod
    def validate_pharmacy_id(cls, v: str | None) -> str | None:
        """Validate pharmacy_id is a valid UUID if provided."""
        if v is None:
            return v
        try:
            UUID(v)
        except ValueError as e:
            raise ValueError(f"pharmacy_id must be a valid UUID: {e}") from e
        return v

    @model_validator(mode="after")
    def validate_rule_fields(self) -> "BypassRuleCreate":
        """Ensure correct fields are set based on rule_type."""
        if self.rule_type == "phone_number":
            if not self.pattern:
                raise ValueError("pattern is required for phone_number rule type")
            if not self.pattern.replace("*", "").replace("+", "").isalnum():
                raise ValueError("pattern must be alphanumeric with optional * wildcard and + prefix")

        elif self.rule_type == "phone_number_list":
            if not self.phone_numbers or len(self.phone_numbers) == 0:
                raise ValueError("phone_numbers is required for phone_number_list rule type")
            if len(self.phone_numbers) > 1000:
                raise ValueError("phone_numbers list cannot exceed 1000 entries")

        elif self.rule_type == "whatsapp_phone_number_id":
            if not self.phone_number_id:
                raise ValueError("phone_number_id is required for whatsapp_phone_number_id rule type")

        # Require pharmacy_id when target_domain is 'pharmacy'
        if self.target_domain == "pharmacy" and not self.pharmacy_id:
            raise ValueError("pharmacy_id is required when target_domain is 'pharmacy'")

        return self


class BypassRuleUpdate(BaseModel):
    """Schema for updating a bypass rule (all fields optional)."""

    rule_name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Human-readable name for the rule",
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Description of what this rule does",
    )
    pattern: str | None = Field(
        None,
        max_length=100,
        description="Pattern for phone_number type",
    )
    phone_numbers: list[str] | None = Field(
        None,
        description="List of phone numbers for phone_number_list type",
    )
    phone_number_id: str | None = Field(
        None,
        max_length=100,
        description="WhatsApp Business phone number ID",
    )
    target_agent: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Agent key to route to",
    )
    target_domain: str | None = Field(
        None,
        max_length=50,
        description="Optional domain override",
    )
    pharmacy_id: str | None = Field(
        None,
        description="Pharmacy ID to link this rule to",
    )
    priority: int | None = Field(
        None,
        ge=-100,
        le=100,
        description="Priority for rule evaluation",
    )
    enabled: bool | None = Field(
        None,
        description="Whether this rule is active",
    )
    isolated_history: bool | None = Field(
        None,
        description="When true, creates isolated conversation history separate from other agents",
    )


class BypassRuleResponse(BaseModel):
    """Schema for bypass rule response."""

    id: str
    organization_id: str
    rule_name: str
    description: str | None
    rule_type: str
    pattern: str | None
    phone_numbers: list[str] | None
    phone_number_id: str | None
    target_agent: str
    target_domain: str | None
    pharmacy_id: str | None
    priority: int
    enabled: bool
    isolated_history: bool | None
    created_at: str | None
    updated_at: str | None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class BypassRuleListResponse(BaseModel):
    """Schema for paginated bypass rules list."""

    rules: list[BypassRuleResponse]
    total: int
    enabled_count: int
    disabled_count: int


class BypassRuleTestRequest(BaseModel):
    """Schema for testing bypass routing."""

    wa_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="WhatsApp ID (phone number) to test",
    )
    whatsapp_phone_number_id: str | None = Field(
        None,
        max_length=50,
        description="WhatsApp Business phone number ID to test",
    )


class BypassRuleTestResponse(BaseModel):
    """Schema for bypass routing test result."""

    matched: bool = Field(
        ...,
        description="Whether any rule matched the input",
    )
    matched_rule: BypassRuleResponse | None = Field(
        None,
        description="The rule that matched (if any)",
    )
    target_agent: str | None = Field(
        None,
        description="Agent that would be routed to",
    )
    target_domain: str | None = Field(
        None,
        description="Domain that would be used",
    )
    evaluation_order: list[str] = Field(
        default_factory=list,
        description="List of rule names in evaluation order",
    )


__all__ = [
    "BypassRuleCreate",
    "BypassRuleUpdate",
    "BypassRuleResponse",
    "BypassRuleListResponse",
    "BypassRuleTestRequest",
    "BypassRuleTestResponse",
]
