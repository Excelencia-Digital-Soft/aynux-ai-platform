"""
AuthRequirementService - Database-driven authentication requirement detection.

Determines which intents and flows require user authentication using
configuration loaded from database. No hardcoded lists allowed.

Usage:
    service = AuthRequirementService()
    requires_auth = await service.intent_requires_auth("debt_query", db, org_id)
    requires_auth = await service.flow_requires_auth("payment_link", db, org_id)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.cache.domain_intent_cache import domain_intent_cache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuthRequirementService:
    """
    Database-driven service for authentication requirements.

    Determines which intents/flows require user identification
    using patterns loaded from database.

    Intent authentication is determined by:
    1. Intent keywords containing "auth_required" keyword
    2. Intent being in the "auth_required" category (via keywords)

    This replaces hardcoded sets like:
    - auth_required_intents = {"debt_query", "payment_link", ...}
    - auth_required_flows = {"debt_query", "payment_link", ...}
    """

    DOMAIN_KEY = "pharmacy"
    AUTH_REQUIRED_KEYWORD = "auth_required"

    def __init__(self) -> None:
        """Initialize service."""
        self._cache: dict[UUID, set[str]] = {}

    async def intent_requires_auth(
        self,
        intent: str,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if an intent requires authentication.

        Args:
            intent: Intent key to check
            db: Optional database session
            organization_id: Tenant UUID

        Returns:
            True if intent requires authentication
        """
        if not intent or not organization_id:
            return False

        auth_intents = await self._get_auth_required_intents(db, organization_id)
        return intent in auth_intents

    async def flow_requires_auth(
        self,
        flow: str,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> bool:
        """
        Check if a flow requires authentication.

        Flows map to intents, so this is equivalent to intent_requires_auth.

        Args:
            flow: Flow name (maps to intent key)
            db: Optional database session
            organization_id: Tenant UUID

        Returns:
            True if flow requires authentication
        """
        return await self.intent_requires_auth(flow, db, organization_id)

    async def get_auth_required_intents(
        self,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> set[str]:
        """
        Get all intents that require authentication.

        Args:
            db: Optional database session
            organization_id: Tenant UUID

        Returns:
            Set of intent keys requiring authentication
        """
        if not organization_id:
            return set()
        return await self._get_auth_required_intents(db, organization_id)

    async def _get_auth_required_intents(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> set[str]:
        """
        Get intents requiring auth from cache/database.

        Intents are marked as auth-required by having "auth_required"
        in their keywords list.

        Args:
            db: Optional database session
            organization_id: Tenant UUID

        Returns:
            Set of intent keys requiring authentication
        """
        # Get all patterns from cache
        all_patterns = await domain_intent_cache.get_patterns(
            db, organization_id, self.DOMAIN_KEY
        )

        auth_intents: set[str] = set()

        # Check each intent for auth_required keyword
        keyword_patterns = all_patterns.get("keyword_patterns", {})
        for intent_key, keywords in keyword_patterns.items():
            if self.AUTH_REQUIRED_KEYWORD in keywords:
                auth_intents.add(intent_key)

        if not auth_intents:
            logger.debug(
                f"No auth-required intents found for org {organization_id}. "
                f"Add '{self.AUTH_REQUIRED_KEYWORD}' keyword to intents that need auth."
            )

        return auth_intents


# Singleton instance for convenience
auth_requirement_service = AuthRequirementService()


__all__ = ["AuthRequirementService", "auth_requirement_service"]
