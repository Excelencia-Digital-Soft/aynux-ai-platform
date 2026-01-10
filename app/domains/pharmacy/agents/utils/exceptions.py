# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Excepciones específicas del dominio pharmacy para el
#              PharmacyResponseGenerator y componentes relacionados.
# Tenant-Aware: Yes - las excepciones incluyen contexto de organización.
# ============================================================================
"""
Pharmacy Domain Exceptions - Custom exceptions for pharmacy agents.

This module defines exceptions used by the pharmacy response generation system.
All exceptions include organization context for debugging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass


class PharmacyDomainError(Exception):
    """Base exception for pharmacy domain errors."""

    pass


class ResponseConfigNotFoundError(PharmacyDomainError):
    """
    Raised when response configuration is not found in database.

    This is an EXPLICIT error - NO DEFAULTS should be used.
    All intents MUST be configured in the database.

    Attributes:
        intent_key: The intent that was not found
        organization_id: The organization where lookup failed
        message: Human-readable error message
    """

    def __init__(
        self,
        intent_key: str,
        organization_id: UUID | str,
        message: str | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            intent_key: The intent that was not found
            organization_id: The organization UUID where lookup failed
            message: Optional custom message
        """
        self.intent_key = intent_key
        self.organization_id = str(organization_id)

        if message is None:
            message = (
                f"No response configuration found for intent '{intent_key}' "
                f"in organization '{organization_id}'. "
                "All intents MUST be configured in database. "
                "Use Admin API to seed/create configurations."
            )

        self.message = message
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"ResponseConfigNotFoundError("
            f"intent_key='{self.intent_key}', "
            f"organization_id='{self.organization_id}')"
        )


class TemplateNotFoundError(PharmacyDomainError):
    """
    Raised when a template file or key is not found.

    Attributes:
        template_key: The template that was not found
        template_type: Type of template (critical, fallback, system)
    """

    def __init__(
        self,
        template_key: str,
        template_type: str = "fallback",
        message: str | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            template_key: The template key that was not found
            template_type: Type of template (critical, fallback, system)
            message: Optional custom message
        """
        self.template_key = template_key
        self.template_type = template_type

        if message is None:
            message = (
                f"Template '{template_key}' not found in {template_type}_templates.yaml. "
                "Ensure the template exists before using it."
            )

        self.message = message
        super().__init__(self.message)


__all__ = [
    "PharmacyDomainError",
    "ResponseConfigNotFoundError",
    "TemplateNotFoundError",
]
