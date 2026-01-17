# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Organization ID resolution and normalization.
#              Extracted from debt_manager_node.py for SRP compliance.
# Tenant-Aware: Yes - handles multi-tenant organization ID parsing.
# ============================================================================
"""
Organization ID resolution and normalization.

This module provides utilities for normalizing organization_id values
from various formats (string, UUID, None) to a consistent UUID format.

Single Responsibility: Organization ID normalization.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

# System organization ID (used when no specific organization is provided)
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


class OrganizationResolver:
    """
    Resolves and normalizes organization_id values.

    Single Responsibility: Convert various organization_id formats to UUID.

    This class handles:
    - None → SYSTEM_ORG_ID
    - String → UUID conversion
    - UUID passthrough
    """

    @staticmethod
    def resolve(org_id_raw: str | UUID | None) -> UUID:
        """
        Normalize organization_id to UUID.

        Args:
            org_id_raw: Organization ID in various formats:
                - None: Returns SYSTEM_ORG_ID
                - str: Converts to UUID
                - UUID: Returns as-is

        Returns:
            Normalized UUID for the organization

        Raises:
            ValueError: If string cannot be parsed as UUID
        """
        if not org_id_raw:
            logger.debug("No organization_id provided, using SYSTEM_ORG_ID")
            return SYSTEM_ORG_ID

        if isinstance(org_id_raw, UUID):
            return org_id_raw

        try:
            return UUID(str(org_id_raw))
        except ValueError as e:
            logger.warning(f"Invalid organization_id format: {org_id_raw}, using SYSTEM_ORG_ID")
            raise ValueError(f"Invalid organization_id: {org_id_raw}") from e

    @staticmethod
    def resolve_safe(org_id_raw: str | UUID | None) -> UUID:
        """
        Normalize organization_id to UUID with fallback.

        Like resolve(), but falls back to SYSTEM_ORG_ID on invalid input
        instead of raising an exception.

        Args:
            org_id_raw: Organization ID in various formats

        Returns:
            Normalized UUID for the organization (never raises)
        """
        try:
            return OrganizationResolver.resolve(org_id_raw)
        except ValueError:
            return SYSTEM_ORG_ID
