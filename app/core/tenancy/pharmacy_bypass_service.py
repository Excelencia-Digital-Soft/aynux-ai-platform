# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio para gestionar bypass rules asociadas a farmacias.
#              Auto-crea, actualiza y elimina bypass rules cuando cambia
#              el whatsapp_phone_number de una farmacia.
# Tenant-Aware: Yes - opera sobre bypass rules por organización.
# ============================================================================
"""
PharmacyBypassService - Auto-manage bypass rules for pharmacies.

Handles the lifecycle of bypass rules linked to pharmacy configurations:
- Creates bypass rules when pharmacy has whatsapp_phone_number
- Updates bypass rules when pharmacy phone number changes
- Deletes bypass rules when pharmacy is deleted or phone removed

Usage:
    # In pharmacy CRUD endpoints
    bypass_service = PharmacyBypassService(db_session)

    # On create
    await bypass_service.create_bypass_rule_for_pharmacy(pharmacy)

    # On update
    await bypass_service.update_bypass_rule_for_pharmacy(pharmacy, old_number)

    # On delete
    await bypass_service.delete_bypass_rule_for_pharmacy(pharmacy_id)
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy import BypassRule, PharmacyMerchantConfig

logger = logging.getLogger(__name__)

# Default configuration for auto-created pharmacy bypass rules
DEFAULT_TARGET_AGENT = "pharmacy_operations_agent"
DEFAULT_PRIORITY = 100


class PharmacyBypassService:
    """
    Service for managing pharmacy-linked bypass rules.

    Automatically creates and manages bypass rules that route WhatsApp
    messages to the correct agent based on the receiving phone number.

    Attributes:
        _db: SQLAlchemy async session for database operations
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy async session for database queries
        """
        self._db = db

    async def create_bypass_rule_for_pharmacy(
        self,
        pharmacy: PharmacyMerchantConfig,
        target_agent: str = DEFAULT_TARGET_AGENT,
        priority: int = DEFAULT_PRIORITY,
    ) -> BypassRule | None:
        """
        Create a bypass rule for a pharmacy if it has a whatsapp_phone_number.

        The rule will route messages received at the pharmacy's WhatsApp number
        directly to the specified agent.

        Args:
            pharmacy: The pharmacy configuration to create rule for
            target_agent: Agent key to route to (default: pharmacy_operations_agent)
            priority: Rule priority (default: 100)

        Returns:
            Created BypassRule, or None if pharmacy has no WhatsApp number
        """
        if not pharmacy.whatsapp_phone_number:
            logger.debug(
                f"Pharmacy {pharmacy.id} has no WhatsApp number, skipping bypass rule creation"
            )
            return None

        rule = BypassRule.create_pharmacy_bypass_rule(
            organization_id=pharmacy.organization_id,
            pharmacy_id=pharmacy.id,
            phone_number_id=pharmacy.whatsapp_phone_number,
            pharmacy_name=pharmacy.pharmacy_name,
            target_agent=target_agent,
            priority=priority,
        )
        self._db.add(rule)

        logger.info(
            f"Created bypass rule '{rule.rule_name}' for pharmacy {pharmacy.id} "
            f"(phone: {pharmacy.whatsapp_phone_number} → {target_agent})"
        )
        return rule

    async def update_bypass_rule_for_pharmacy(
        self,
        pharmacy: PharmacyMerchantConfig,
        old_whatsapp_number: str | None,
    ) -> BypassRule | None:
        """
        Update or create/delete bypass rule based on whatsapp_phone_number changes.

        Handles the following scenarios:
        - No change: Do nothing
        - Number added (was None): Create new bypass rule
        - Number changed: Update existing rule's phone_number_id
        - Number removed (now None): Delete existing bypass rule

        Args:
            pharmacy: The pharmacy configuration with updated data
            old_whatsapp_number: The previous WhatsApp number (before update)

        Returns:
            Updated/created BypassRule, or None if rule was deleted/not needed
        """
        new_number = pharmacy.whatsapp_phone_number

        # No change - do nothing
        if old_whatsapp_number == new_number:
            return None

        # Find existing rule for this pharmacy
        existing_rule = await self._get_rule_for_pharmacy(pharmacy.id)

        # Number removed - delete rule
        if not new_number:
            if existing_rule:
                await self._db.delete(existing_rule)
                logger.info(
                    f"Deleted bypass rule for pharmacy {pharmacy.id} (WhatsApp number removed)"
                )
            return None

        # Number added or changed
        if existing_rule:
            # Update existing rule with new phone number
            existing_rule.phone_number_id = new_number
            logger.info(
                f"Updated bypass rule phone_number_id for pharmacy {pharmacy.id}: "
                f"{old_whatsapp_number} → {new_number}"
            )
            return existing_rule
        else:
            # Create new rule (number was added)
            return await self.create_bypass_rule_for_pharmacy(pharmacy)

    async def delete_bypass_rule_for_pharmacy(
        self,
        pharmacy_id: UUID,
    ) -> bool:
        """
        Delete bypass rule associated with a pharmacy.

        Called when a pharmacy is being deleted. While the FK has ON DELETE SET NULL,
        we explicitly delete the rule to keep the database clean.

        Args:
            pharmacy_id: ID of the pharmacy being deleted

        Returns:
            True if a rule was deleted, False if no rule existed
        """
        rule = await self._get_rule_for_pharmacy(pharmacy_id)
        if rule:
            await self._db.delete(rule)
            logger.info(f"Deleted bypass rule for pharmacy {pharmacy_id}")
            return True

        logger.debug(f"No bypass rule found for pharmacy {pharmacy_id}")
        return False

    async def _get_rule_for_pharmacy(
        self,
        pharmacy_id: UUID,
    ) -> BypassRule | None:
        """
        Get bypass rule linked to a pharmacy.

        Args:
            pharmacy_id: ID of the pharmacy

        Returns:
            BypassRule if found, None otherwise
        """
        stmt = select(BypassRule).where(BypassRule.pharmacy_id == pharmacy_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
