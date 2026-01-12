"""
Auth Level Service

Domain service for determining authentication level for context-based ofuscation.
Used to control how much debt detail is shown based on customer verification strength.
"""

from __future__ import annotations

from typing import Any


class AuthLevel:
    """Authentication level constants for debt display ofuscation."""

    STRONG = "STRONG"  # Phone matches PLEX (is_self=True) - full details
    MEDIUM = "MEDIUM"  # Phone has registered persons - ofuscated
    WEAK = "WEAK"  # DNI+Name validation only - ofuscated


class AuthLevelService:
    """
    Domain service for determining authentication level.

    Auth Levels determine how much detail to show in debt responses:
    - STRONG: Phone matches PLEX customer directly → show full invoice details
    - MEDIUM: Phone has registered persons in DB → ofuscated view
    - WEAK: Validated via DNI+Name only → ofuscated view

    Single Responsibility: Determine authentication level from state.
    """

    @classmethod
    def determine_level(cls, state: dict[str, Any]) -> str:
        """
        Determine authentication level from conversation state.

        Args:
            state: Current conversation state dictionary

        Returns:
            Auth level string (STRONG, MEDIUM, or WEAK)
        """
        # STRONG: Direct phone match with PLEX customer
        if state.get("is_self", False):
            return AuthLevel.STRONG

        # MEDIUM: Has active registered person from DB
        if state.get("active_registered_person_id"):
            return AuthLevel.MEDIUM

        # WEAK: Validated via DNI+Name only (default)
        return AuthLevel.WEAK

    @classmethod
    def should_show_full_details(cls, auth_level: str) -> bool:
        """
        Check if auth level allows showing full debt details.

        Args:
            auth_level: Authentication level string

        Returns:
            True if full details should be shown
        """
        return auth_level == AuthLevel.STRONG

    @classmethod
    def should_ofuscate(cls, auth_level: str) -> bool:
        """
        Check if debt details should be ofuscated.

        Args:
            auth_level: Authentication level string

        Returns:
            True if details should be ofuscated
        """
        return auth_level in (AuthLevel.MEDIUM, AuthLevel.WEAK)
