"""
Contact Domain Use Cases.

Use cases for managing contact-domain assignments.
"""

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.contact_domains import ContactDomain

logger = logging.getLogger(__name__)

# Available domains (TODO: Replace with DomainRegistry to load from DB)
AVAILABLE_DOMAINS = ["excelencia", "pharmacy", "ecommerce", "healthcare", "credit"]


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

    async def execute(self, wa_id: str) -> dict[str, Any]:
        """
        Get contact's assigned domain.

        Args:
            wa_id: WhatsApp ID of the contact

        Returns:
            Contact domain information or not-assigned status
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
    ) -> dict[str, Any]:
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
        """
        try:
            if domain not in AVAILABLE_DOMAINS:
                raise ValueError(f"Domain '{domain}' not available")

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

    async def execute(self, wa_id: str) -> dict[str, Any]:
        """
        Remove domain assignment.

        Args:
            wa_id: WhatsApp ID

        Returns:
            Removal confirmation

        Raises:
            ValueError: If contact has no assignment
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

    async def execute(self, wa_id: str | None = None) -> dict[str, Any]:
        """
        Clear domain assignments.

        Args:
            wa_id: Optional WhatsApp ID. If None, clears all assignments.

        Returns:
            Deletion confirmation with count

        Raises:
            ValueError: If specific contact not found
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
