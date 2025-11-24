"""
Admin Use Cases

Use cases for system administration and domain management following Clean Architecture.
These Use Cases replace the legacy domain_detector and domain_manager services.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.contact_domains import ContactDomain, DomainConfig

logger = logging.getLogger(__name__)


# ============================================================
# DOMAIN CONFIGURATION MANAGEMENT
# ============================================================


class ListDomainsUseCase:
    """
    Use Case: List all available domains with their configuration.

    Responsibilities:
    - Query database for domain configurations
    - Get available domains from system registry
    - Combine configuration data with availability status
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize use case.

        Args:
            db: Async database session
        """
        self.db = db

    async def execute(self) -> Dict[str, Any]:
        """
        List all domains with configuration and status.

        Returns:
            Dictionary with domains list and counts

        Example:
            use_case = ListDomainsUseCase(db)
            result = await use_case.execute()
            # Returns: {"domains": [...], "total": 3, ...}
        """
        try:
            # Query all domain configurations from database
            query = select(DomainConfig)
            result = await self.db.execute(query)
            configs = result.scalars().all()

            # Get available domains from system registry
            # TODO: Replace with DomainRegistry when implemented
            available_domains = ["ecommerce", "healthcare", "credit"]  # Hardcoded for now

            # Combine information
            domains_info = []
            for config in configs:
                domain_info = config.to_dict()
                domain_info.update({
                    "available": config.domain in available_domains,
                    "initialized": True,  # Simplified for now
                })
                domains_info.append(domain_info)

            # Add registered domains without database configuration
            configured_domains = {config.domain for config in configs}
            for domain in available_domains:
                if domain not in configured_domains:
                    domains_info.append({
                        "domain": domain,
                        "enabled": "true",
                        "display_name": domain.title(),
                        "available": True,
                        "initialized": True,
                        "note": "No database configuration found",
                    })

            return {
                "domains": domains_info,
                "total": len(domains_info),
                "available_count": len(available_domains),
                "initialized_count": len(available_domains),
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

    async def execute(self, domain: str) -> Dict[str, Any]:
        """
        Enable a domain.

        Args:
            domain: Domain identifier (e.g., "ecommerce", "healthcare")

        Returns:
            Success status and domain info

        Raises:
            ValueError: If domain is invalid

        Example:
            use_case = EnableDomainUseCase(db)
            result = await use_case.execute("healthcare")
        """
        try:
            # Validate domain
            available_domains = ["ecommerce", "healthcare", "credit"]
            if domain not in available_domains:
                raise ValueError(f"Domain '{domain}' not found")

            # Get or create domain configuration
            query = select(DomainConfig).where(DomainConfig.domain == domain)
            result = await self.db.execute(query)
            config = result.scalar_one_or_none()

            if config:
                config.enabled = "true"  # type: ignore[assignment]
            else:
                # Create new configuration
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

    async def execute(self, domain: str) -> Dict[str, Any]:
        """
        Disable a domain.

        Args:
            domain: Domain identifier

        Returns:
            Success status and domain info

        Raises:
            ValueError: If domain is default or not found

        Example:
            use_case = DisableDomainUseCase(db)
            result = await use_case.execute("healthcare")
        """
        try:
            # Prevent disabling default domain
            if domain == "ecommerce":
                raise ValueError("Cannot disable default domain 'ecommerce'")

            # Get domain configuration
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
        enabled: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        phone_patterns: Optional[List[str]] = None,
        keyword_patterns: Optional[List[str]] = None,
        priority: Optional[float] = None,
    ) -> Dict[str, Any]:
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

        Example:
            use_case = UpdateDomainConfigUseCase(db)
            result = await use_case.execute(
                "healthcare",
                enabled="true",
                priority=2.0
            )
        """
        try:
            # Get domain configuration
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
            return {"status": "success", "domain": domain, "updated_config": config.to_dict()}

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating domain config for {domain}: {e}")
            await self.db.rollback()
            raise


# ============================================================
# CONTACT-DOMAIN ASSIGNMENT
# ============================================================


class GetContactDomainUseCase:
    """
    Use Case: Get domain assignment for a specific contact.

    Responsibilities:
    - Query contact domain assignment
    - Return assignment details or not-assigned status
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self, wa_id: str) -> Dict[str, Any]:
        """
        Get contact's assigned domain.

        Args:
            wa_id: WhatsApp ID of the contact

        Returns:
            Contact domain information or not-assigned status

        Example:
            use_case = GetContactDomainUseCase(db)
            result = await use_case.execute("+5491123456789")
        """
        try:
            query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await self.db.execute(query)
            contact_domain = result.scalar_one_or_none()

            if not contact_domain:
                return {
                    "wa_id": wa_id,
                    "domain": None,
                    "status": "not_assigned",
                    "message": "Contact has no domain assigned",
                }

            return {
                "wa_id": wa_id,
                "domain_info": contact_domain.to_dict(),
                "status": "assigned",
            }

        except Exception as e:
            logger.error(f"Error getting contact domain for {wa_id}: {e}")
            raise


class AssignContactDomainUseCase:
    """
    Use Case: Assign a domain to a contact.

    Responsibilities:
    - Validate domain exists and is available
    - Create or update contact-domain assignment
    - Record assignment method and confidence
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(
        self,
        wa_id: str,
        domain: str,
        method: str = "manual",
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Assign domain to contact.

        Args:
            wa_id: WhatsApp ID
            domain: Domain to assign
            method: Assignment method (e.g., "manual", "auto")
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            Assignment confirmation

        Raises:
            ValueError: If domain is invalid

        Example:
            use_case = AssignContactDomainUseCase(db)
            result = await use_case.execute(
                "+5491123456789",
                "healthcare",
                method="manual",
                confidence=1.0
            )
        """
        try:
            # Validate domain
            available_domains = ["ecommerce", "healthcare", "credit"]
            if domain not in available_domains:
                raise ValueError(f"Domain '{domain}' not available")

            # Check if assignment already exists
            query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await self.db.execute(query)
            contact_domain = result.scalar_one_or_none()

            if contact_domain:
                # Update existing assignment
                contact_domain.domain = domain  # type: ignore[assignment]
                contact_domain.assigned_method = method  # type: ignore[assignment]
                contact_domain.confidence = confidence  # type: ignore[assignment]
            else:
                # Create new assignment
                contact_domain = ContactDomain(
                    wa_id=wa_id,
                    domain=domain,
                    assigned_method=method,
                    confidence=confidence,
                )
                self.db.add(contact_domain)

            await self.db.commit()

            logger.info(f"Domain assigned: {wa_id} -> {domain}")
            return {
                "status": "success",
                "wa_id": wa_id,
                "domain": domain,
                "confidence": confidence,
                "method": method,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error assigning domain to {wa_id}: {e}")
            await self.db.rollback()
            raise


class RemoveContactDomainUseCase:
    """
    Use Case: Remove domain assignment from a contact.

    Responsibilities:
    - Validate contact has assignment
    - Delete contact-domain record
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self, wa_id: str) -> Dict[str, Any]:
        """
        Remove domain assignment.

        Args:
            wa_id: WhatsApp ID

        Returns:
            Removal confirmation

        Raises:
            ValueError: If contact has no assignment

        Example:
            use_case = RemoveContactDomainUseCase(db)
            result = await use_case.execute("+5491123456789")
        """
        try:
            query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await self.db.execute(query)
            contact_domain = result.scalar_one_or_none()

            if not contact_domain:
                raise ValueError(f"Contact '{wa_id}' has no domain assigned")

            await self.db.delete(contact_domain)
            await self.db.commit()

            logger.info(f"Domain assignment removed: {wa_id}")
            return {"status": "success", "wa_id": wa_id, "action": "removed"}

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error removing domain assignment for {wa_id}: {e}")
            await self.db.rollback()
            raise


class ClearDomainAssignmentsUseCase:
    """
    Use Case: Clear domain assignments (all or specific contact).

    Responsibilities:
    - Clear single contact assignment or all assignments
    - Handle bulk deletion safely
    """

    def __init__(self, db: AsyncSession):
        """Initialize use case."""
        self.db = db

    async def execute(self, wa_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear domain assignments.

        Args:
            wa_id: Optional WhatsApp ID. If None, clears all assignments.

        Returns:
            Deletion confirmation with count

        Raises:
            ValueError: If specific contact not found

        Example:
            # Clear specific contact
            use_case = ClearDomainAssignmentsUseCase(db)
            result = await use_case.execute("+5491123456789")

            # Clear all assignments
            result = await use_case.execute()
        """
        try:
            if wa_id:
                # Clear specific contact
                query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
                result = await self.db.execute(query)
                contact_domain = result.scalar_one_or_none()

                if not contact_domain:
                    raise ValueError(f"No domain assignment found for {wa_id}")

                await self.db.delete(contact_domain)
                await self.db.commit()

                message = f"Domain assignment cleared for {wa_id}"
                return {
                    "status": "success",
                    "action": "assignment_cleared",
                    "wa_id": wa_id,
                    "message": message,
                }
            else:
                # Clear all assignments (dangerous operation)
                query = delete(ContactDomain)
                result = await self.db.execute(query)
                await self.db.commit()

                deleted_count = result.rowcount
                message = f"All domain assignments cleared ({deleted_count} entries)"
                logger.warning(message)

                return {
                    "status": "success",
                    "action": "all_assignments_cleared",
                    "deleted_count": deleted_count,
                    "message": message,
                }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error clearing domain assignments: {e}")
            await self.db.rollback()
            raise


# ============================================================
# DOMAIN STATISTICS & MONITORING
# ============================================================


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

    async def execute(self) -> Dict[str, Any]:
        """
        Get domain statistics.

        Returns:
            Statistics dictionary with counts and breakdowns

        Example:
            use_case = GetDomainStatsUseCase(db)
            stats = await use_case.execute()
            # Returns: {"contacts": {"total_assigned": 150, ...}, ...}
        """
        try:
            # Query all contact-domain assignments
            query = select(
                ContactDomain.domain,
                ContactDomain.assigned_method
            ).order_by(ContactDomain.created_at.desc())

            result = await self.db.execute(query)
            contact_data = result.all()

            # Calculate statistics
            domain_stats: Dict[str, int] = {}
            method_stats: Dict[str, int] = {}

            for domain, method in contact_data:
                # By domain
                if domain not in domain_stats:
                    domain_stats[domain] = 0
                domain_stats[domain] += 1

                # By method
                if method not in method_stats:
                    method_stats[method] = 0
                method_stats[method] += 1

            return {
                "contacts": {
                    "total_assigned": len(contact_data),
                    "by_domain": domain_stats,
                    "by_method": method_stats,
                },
                "available_domains": ["ecommerce", "healthcare", "credit"],
                "initialized_domains": ["ecommerce", "healthcare", "credit"],
            }

        except Exception as e:
            logger.error(f"Error getting domain stats: {e}")
            raise
