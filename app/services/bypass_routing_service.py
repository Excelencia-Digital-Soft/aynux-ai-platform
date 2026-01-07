"""
Bypass Routing Service.

Handles special routing rules that bypass normal domain detection.
Single Responsibility: Phone number pattern matching and organization routing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy import BypassRule, Organization, TenantConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BypassMatch:
    """
    Result of bypass routing evaluation.

    Attributes:
        organization_id: UUID of the matched organization
        domain: Domain to use for message processing
        target_agent: Agent to route the message to
        pharmacy_id: UUID of the pharmacy (if rule is linked to a pharmacy)
        isolated_history: When true, creates isolated conversation history
        rule_id: UUID of the matched rule (used for generating isolated history suffix)
    """

    organization_id: UUID
    domain: str
    target_agent: str
    pharmacy_id: UUID | None = None
    isolated_history: bool = False
    rule_id: UUID | None = None


class BypassRoutingService:
    """
    Service for evaluating bypass routing rules.

    Bypass rules allow specific phone numbers or patterns to be
    routed to specific organizations and agents, bypassing normal
    domain detection logic.

    Rule Types:
    - phone_number: Pattern matching with wildcard (*)
    - phone_number_list: Exact match against list
    - whatsapp_phone_number_id: Match WhatsApp business phone ID

    Rules are loaded from the bypass_rules table, ordered by priority (highest first).
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize service.

        Args:
            db: Async database session
        """
        self._db = db

    async def evaluate_bypass_rules(
        self,
        wa_id: str,
        whatsapp_phone_number_id: str | None = None,
    ) -> BypassMatch | None:
        """
        Evaluate bypass routing rules across all organizations.

        Args:
            wa_id: WhatsApp ID of the incoming message sender
            whatsapp_phone_number_id: WhatsApp Business phone number ID

        Returns:
            BypassMatch if a rule matches, None otherwise
        """
        try:
            logger.info(
                f"[BYPASS] Evaluating rules with wa_id={wa_id}, "
                f"whatsapp_phone_number_id={whatsapp_phone_number_id}"
            )

            # Load all enabled rules ordered by priority
            rules = await self._load_active_rules()
            logger.debug(f"[BYPASS] Loaded {len(rules)} active bypass rules")

            for rule, org, tenant_config in rules:
                if rule.matches(wa_id, whatsapp_phone_number_id):
                    # Use rule's target_domain or fallback to tenant's default_domain
                    domain = (
                        rule.target_domain
                        or (tenant_config.default_domain if tenant_config else None)
                        or "excelencia"
                    )
                    logger.info(
                        f"[BYPASS] Rule '{rule.rule_name}' matched for {wa_id}: "
                        f"org={org.slug}, domain={domain}, agent={rule.target_agent}, "
                        f"pharmacy_id={rule.pharmacy_id}"
                    )
                    return BypassMatch(
                        organization_id=cast(UUID, org.id),
                        domain=cast(str, domain),
                        target_agent=cast(str, rule.target_agent),
                        pharmacy_id=cast(UUID | None, rule.pharmacy_id),
                        isolated_history=bool(rule.isolated_history) if rule.isolated_history else False,
                        rule_id=cast(UUID, rule.id),
                    )

            # No rule matched
            logger.debug(
                f"[BYPASS] No rule matched for wa_id={wa_id}, "
                f"whatsapp_phone_number_id={whatsapp_phone_number_id}, "
                f"evaluated {len(rules)} rules"
            )
            return None

        except Exception as e:
            logger.warning(f"Error checking bypass routing: {e}")
            return None

    async def _load_active_rules(
        self,
    ) -> Sequence[tuple[BypassRule, Organization, TenantConfig | None]]:
        """
        Load all active bypass rules with their organizations.

        Rules are ordered by priority (highest first).

        Returns:
            List of (BypassRule, Organization, TenantConfig) tuples
        """
        query = (
            select(BypassRule, Organization, TenantConfig)
            .join(Organization, BypassRule.organization_id == Organization.id)
            .outerjoin(TenantConfig, TenantConfig.organization_id == Organization.id)
            .where(Organization.status == "active")
            .where(BypassRule.enabled == True)  # noqa: E712
            .order_by(BypassRule.priority.desc(), BypassRule.rule_name)  # type: ignore[union-attr]
        )
        result = await self._db.execute(query)
        return [tuple(row) for row in result.all()]

    async def evaluate_bypass_rules_for_org(
        self,
        organization_id: UUID,
        wa_id: str,
        whatsapp_phone_number_id: str | None = None,
    ) -> BypassMatch | None:
        """
        Evaluate bypass routing rules for a specific organization.

        Args:
            organization_id: Organization UUID to check rules for
            wa_id: WhatsApp ID of the incoming message sender
            whatsapp_phone_number_id: WhatsApp Business phone number ID

        Returns:
            BypassMatch if a rule matches, None otherwise
        """
        try:
            rules = await self._load_rules_for_org(organization_id)

            for rule, tenant_config in rules:
                if rule.matches(wa_id, whatsapp_phone_number_id):
                    domain = (
                        rule.target_domain
                        or (tenant_config.default_domain if tenant_config else None)
                        or "excelencia"
                    )
                    logger.info(
                        f"[BYPASS] Rule '{rule.rule_name}' matched for org {organization_id}, "
                        f"pharmacy_id={rule.pharmacy_id}"
                    )
                    return BypassMatch(
                        organization_id=organization_id,
                        domain=cast(str, domain),
                        target_agent=cast(str, rule.target_agent),
                        pharmacy_id=cast(UUID | None, rule.pharmacy_id),
                        isolated_history=bool(rule.isolated_history) if rule.isolated_history else False,
                        rule_id=cast(UUID, rule.id),
                    )

            return None

        except Exception as e:
            logger.warning(f"Error checking bypass routing for org {organization_id}: {e}")
            return None

    async def _load_rules_for_org(
        self,
        organization_id: UUID,
    ) -> Sequence[tuple[BypassRule, TenantConfig | None]]:
        """
        Load bypass rules for a specific organization.

        Args:
            organization_id: Organization UUID

        Returns:
            List of (BypassRule, TenantConfig) tuples
        """
        query = (
            select(BypassRule, TenantConfig)
            .outerjoin(TenantConfig, TenantConfig.organization_id == BypassRule.organization_id)
            .where(BypassRule.organization_id == organization_id)
            .where(BypassRule.enabled == True)  # noqa: E712
            .order_by(BypassRule.priority.desc(), BypassRule.rule_name)  # type: ignore[union-attr]
        )
        result = await self._db.execute(query)
        return [tuple(row) for row in result.all()]


def get_bypass_routing_service(db: AsyncSession) -> BypassRoutingService:
    """
    Factory function for dependency injection.

    Args:
        db: Async database session

    Returns:
        BypassRoutingService instance
    """
    return BypassRoutingService(db)
