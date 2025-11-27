"""
Domain Management Use Cases.

Use cases for domain configuration and statistics management.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.contact_domains import ContactDomain, DomainConfig

logger = logging.getLogger(__name__)

# Available domains (TODO: Replace with DomainRegistry)
AVAILABLE_DOMAINS = ["ecommerce", "healthcare", "credit"]


class ListDomainsUseCase:
    """
    Use Case: List all available domains with their configuration.

    Responsibilities:
    - Query database for domain configurations
    - Get available domains from system registry
    - Combine configuration data with availability status
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self) -> dict[str, Any]:
        """
        List all domains with configuration and status.

        Returns:
            Dictionary with domains list and counts
        """
        try:
            # Query all domain configurations from database
            query = select(DomainConfig)
            result = await self.db.execute(query)
            configs = result.scalars().all()

            # Combine information
            domains_info = []
            for config in configs:
                domain_info = config.to_dict()
                domain_info.update(
                    {
                        "available": config.domain in AVAILABLE_DOMAINS,
                        "initialized": True,
                    }
                )
                domains_info.append(domain_info)

            # Add registered domains without database configuration
            configured_domains = {config.domain for config in configs}
            for domain in AVAILABLE_DOMAINS:
                if domain not in configured_domains:
                    domains_info.append(
                        {
                            "domain": domain,
                            "enabled": "true",
                            "display_name": domain.title(),
                            "available": True,
                            "initialized": True,
                            "note": "No database configuration found",
                        }
                    )

            return {
                "domains": domains_info,
                "total": len(domains_info),
                "available_count": len(AVAILABLE_DOMAINS),
                "initialized_count": len(AVAILABLE_DOMAINS),
            }

        except Exception as e:
            logger.error(f"Error in ListDomainsUseCase: {e}")
            raise


class EnableDomainUseCase:
    """
    Use Case: Enable a specific domain.

    Responsibilities:
    - Validate domain exists
    - Update or create domain configuration
    - Mark domain as enabled
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self, domain: str) -> dict[str, Any]:
        """
        Enable a domain.

        Args:
            domain: Domain identifier (e.g., "ecommerce", "healthcare")

        Returns:
            Success status and domain info

        Raises:
            ValueError: If domain is invalid
        """
        try:
            if domain not in AVAILABLE_DOMAINS:
                raise ValueError(f"Domain '{domain}' not found")

            # Get or create domain configuration
            query = select(DomainConfig).where(DomainConfig.domain == domain)
            result = await self.db.execute(query)
            config = result.scalar_one_or_none()

            if config:
                config.enabled = "true"  # type: ignore[assignment]
            else:
                config = DomainConfig(
                    domain=domain,
                    enabled="true",
                    display_name=domain.title(),
                    description=f"Auto-generated configuration for {domain}",
                )
                self.db.add(config)

            await self.db.commit()

            logger.info(f"Domain enabled: {domain}")
            return {"status": "success", "domain": domain, "enabled": True}

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error enabling domain {domain}: {e}")
            await self.db.rollback()
            raise


class DisableDomainUseCase:
    """
    Use Case: Disable a specific domain.

    Responsibilities:
    - Validate domain can be disabled (not default)
    - Update domain configuration
    - Mark domain as disabled
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self, domain: str) -> dict[str, Any]:
        """
        Disable a domain.

        Args:
            domain: Domain identifier

        Returns:
            Success status and domain info

        Raises:
            ValueError: If domain is default or not found
        """
        try:
            if domain == "ecommerce":
                raise ValueError("Cannot disable default domain 'ecommerce'")

            query = select(DomainConfig).where(DomainConfig.domain == domain)
            result = await self.db.execute(query)
            config = result.scalar_one_or_none()

            if not config:
                raise ValueError(f"Domain configuration '{domain}' not found")

            config.enabled = "false"  # type: ignore[assignment]
            await self.db.commit()

            logger.info(f"Domain disabled: {domain}")
            return {"status": "success", "domain": domain, "enabled": False}

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error disabling domain {domain}: {e}")
            await self.db.rollback()
            raise


class UpdateDomainConfigUseCase:
    """
    Use Case: Update domain configuration.

    Responsibilities:
    - Validate domain exists
    - Update configuration fields
    - Persist changes
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(
        self,
        domain: str,
        enabled: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        phone_patterns: list[str] | None = None,
        keyword_patterns: list[str] | None = None,
        priority: float | None = None,
    ) -> dict[str, Any]:
        """
        Update domain configuration.

        Args:
            domain: Domain identifier
            enabled: Enable/disable status
            display_name: Display name
            description: Description
            phone_patterns: Phone number patterns
            keyword_patterns: Keyword patterns
            priority: Priority level

        Returns:
            Updated configuration

        Raises:
            ValueError: If domain not found
        """
        try:
            query = select(DomainConfig).where(DomainConfig.domain == domain)
            result = await self.db.execute(query)
            config = result.scalar_one_or_none()

            if not config:
                raise ValueError(f"Domain configuration '{domain}' not found")

            # Update provided fields
            if enabled is not None:
                config.enabled = enabled  # type: ignore[assignment]
            if display_name is not None:
                config.display_name = display_name  # type: ignore[assignment]
            if description is not None:
                config.description = description  # type: ignore[assignment]
            if phone_patterns is not None:
                config.phone_patterns = phone_patterns  # type: ignore[assignment]
            if keyword_patterns is not None:
                config.keyword_patterns = keyword_patterns  # type: ignore[assignment]
            if priority is not None:
                config.priority = priority  # type: ignore[assignment]

            await self.db.commit()

            logger.info(f"Domain configuration updated: {domain}")
            return {
                "status": "success",
                "domain": domain,
                "updated_config": config.to_dict(),
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating domain config for {domain}: {e}")
            await self.db.rollback()
            raise


class GetDomainStatsUseCase:
    """
    Use Case: Get domain system statistics.

    Responsibilities:
    - Query contact-domain assignments
    - Calculate statistics by domain and method
    - Aggregate metrics
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self) -> dict[str, Any]:
        """
        Get domain statistics.

        Returns:
            Statistics dictionary with counts and breakdowns
        """
        try:
            query = select(
                ContactDomain.domain, ContactDomain.assigned_method
            ).order_by(ContactDomain.created_at.desc())

            result = await self.db.execute(query)
            contact_data = result.all()

            # Calculate statistics
            domain_stats: dict[str, int] = {}
            method_stats: dict[str, int] = {}

            for domain, method in contact_data:
                if domain not in domain_stats:
                    domain_stats[domain] = 0
                domain_stats[domain] += 1

                if method not in method_stats:
                    method_stats[method] = 0
                method_stats[method] += 1

            return {
                "contacts": {
                    "total_assigned": len(contact_data),
                    "by_domain": domain_stats,
                    "by_method": method_stats,
                },
                "available_domains": AVAILABLE_DOMAINS,
                "initialized_domains": AVAILABLE_DOMAINS,
            }

        except Exception as e:
            logger.error(f"Error getting domain stats: {e}")
            raise
