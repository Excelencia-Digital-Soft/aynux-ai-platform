# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Configuration loader for pharmacy domain settings.
#              Loads threshold and other settings from database.
# Tenant-Aware: Yes - loads configuration per organization_id.
# ============================================================================
"""
Pharmacy Config Loader - Database-driven configuration for pharmacy nodes.

Provides utilities to load configuration values from the database,
avoiding hardcoded values in node implementations.

Usage:
    from app.domains.pharmacy.agents.utils.config_loader import PharmacyConfigLoader

    # Get name matching threshold from DB
    threshold = await PharmacyConfigLoader.get_name_match_threshold(db, org_id)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default threshold when DB config is not available (emergency fallback only)
DEFAULT_NAME_MATCH_THRESHOLD = 0.7


class PharmacyConfigLoader:
    """
    Loads pharmacy configuration from database.

    Uses PharmacyMerchantConfig table for pharmacy-specific settings.
    Includes caching to avoid repeated DB queries.

    All methods are class methods for easy usage.
    """

    _cache: dict[str, float] = {}

    @classmethod
    async def get_name_match_threshold(
        cls,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> float:
        """
        Get name matching threshold from DB config.

        The threshold determines the minimum score for fuzzy name matching.
        Values range from 0.0 to 1.0 (0.7 = 70% match required).

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            Threshold value (0.0 to 1.0)

        Note:
            If the config is not found in DB, returns DEFAULT_NAME_MATCH_THRESHOLD
            with a warning log. This should be treated as an emergency fallback.
        """
        cache_key = f"{organization_id}:name_match_threshold"

        if cache_key in cls._cache:
            return cls._cache[cache_key]

        threshold = DEFAULT_NAME_MATCH_THRESHOLD

        if db is not None:
            try:
                from sqlalchemy import select

                from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig

                stmt = (
                    select(PharmacyMerchantConfig)
                    .where(PharmacyMerchantConfig.organization_id == organization_id)
                    .limit(1)
                )
                result = await db.execute(stmt)
                config = result.scalar_one_or_none()

                if config is not None:
                    # Check if the column exists (added in migration)
                    if hasattr(config, "name_match_threshold") and config.name_match_threshold is not None:
                        threshold = float(cast(Any, config.name_match_threshold))
                        logger.debug(f"Loaded name_match_threshold={threshold} from DB for org {organization_id}")
                    else:
                        logger.debug(
                            f"name_match_threshold not set in DB for org {organization_id}, using default {threshold}"
                        )
                else:
                    logger.warning(
                        f"No pharmacy config found for org {organization_id}, using default threshold {threshold}"
                    )

            except Exception as e:
                logger.warning(f"Error loading pharmacy config for org {organization_id}: {e}")

        cls._cache[cache_key] = threshold
        return threshold

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the in-memory cache."""
        cls._cache.clear()

    @classmethod
    def invalidate(cls, organization_id: UUID) -> None:
        """Invalidate cache for a specific organization."""
        keys_to_remove = [k for k in cls._cache if str(organization_id) in k]
        for key in keys_to_remove:
            del cls._cache[key]


__all__ = ["PharmacyConfigLoader", "DEFAULT_NAME_MATCH_THRESHOLD"]
