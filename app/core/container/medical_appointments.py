# ============================================================================
# SCOPE: DOMAIN
# Description: Container for Medical Appointments domain dependencies.
#              Provides factories for agents, use cases, and repositories.
# Tenant-Aware: Yes - all configuration comes from database per-institution.
# ============================================================================
"""
Medical Appointments Domain Container.

Provides dependency injection for the Medical Appointments domain.

IMPORTANT: This container does NOT provide default configuration.
All configuration MUST come from the database via InstitutionConfigService.
The agent requires institution_config to be injected via bypass routing state.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer
    from app.core.tenancy.institution_config_service import InstitutionConfig
    from app.domains.medical_appointments.agents import MedicalAppointmentsAgent
    from app.domains.medical_appointments.infrastructure.external.hcweb_soap_client import (
        HCWebSOAPClient,
    )

logger = logging.getLogger(__name__)


class MedicalAppointmentsContainer:
    """Container for Medical Appointments domain dependencies.

    Single Responsibility: Wire medical appointments dependencies.

    NOTE: This container does NOT store any institution-specific configuration.
    All configuration must come from the database via InstitutionConfigService
    and be passed explicitly to factory methods.
    """

    def __init__(self, base: "BaseContainer"):
        """Initialize container.

        Args:
            base: Base container with shared singletons.
        """
        self._base = base
        logger.debug("MedicalAppointmentsContainer initialized (no default config)")

    def create_soap_client(
        self,
        institution_config: "InstitutionConfig",
    ) -> "HCWebSOAPClient":
        """Create HCWeb SOAP client from institution config.

        Args:
            institution_config: Institution configuration from database.

        Returns:
            Configured HCWebSOAPClient instance.

        Raises:
            ValueError: If institution_config has no base_url configured.
        """
        from app.domains.medical_appointments.infrastructure.external.hcweb_soap_client import (
            HCWebSOAPClient,
        )

        base_url = institution_config.base_url
        if not base_url:
            raise ValueError(
                f"Institution '{institution_config.institution_key}' has no base_url configured. "
                f"Configure connection.base_url in tenant_institution_configs table."
            )

        return HCWebSOAPClient(
            base_url=base_url,
            institution_id=institution_config.institution_key,
            timeout=institution_config.timeout_seconds,
        )

    def create_medical_appointments_agent(
        self,
        config: dict[str, Any] | None = None,
    ) -> "MedicalAppointmentsAgent":
        """Create Medical Appointments agent.

        NOTE: The agent will require institution_config to be injected via
        the state dict at runtime (from bypass routing). This factory
        does not provide default configuration.

        Args:
            config: Optional configuration overrides for the agent.

        Returns:
            MedicalAppointmentsAgent instance.
        """
        from app.domains.medical_appointments.agents import MedicalAppointmentsAgent

        return MedicalAppointmentsAgent(
            name="medical_appointments_agent",
            config=config or {},
        )

    def create_medical_appointments_agent_with_config(
        self,
        institution_config: "InstitutionConfig",
    ) -> "MedicalAppointmentsAgent":
        """Create Medical Appointments agent with explicit institution config.

        Use this when you have the institution config available at creation time.

        Args:
            institution_config: Institution configuration from database.

        Returns:
            Configured MedicalAppointmentsAgent instance.
        """
        from app.domains.medical_appointments.agents import MedicalAppointmentsAgent

        agent_config = {
            "institution": institution_config.institution_key,
            "institution_id": institution_config.institution_key,
            "institution_name": institution_config.institution_name,
            "soap_url": institution_config.base_url,
            "base_url": institution_config.base_url,
            "connection_type": institution_config.connection_type,
            "timeout_seconds": institution_config.timeout_seconds,
            "timezone": institution_config.timezone,
        }

        return MedicalAppointmentsAgent(
            name="medical_appointments_agent",
            config=agent_config,
        )
