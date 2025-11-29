"""
Agents Container.

Single Responsibility: Wire all domain agents and orchestrator.
"""

import logging
from typing import TYPE_CHECKING

from app.core.interfaces.agent import IAgent
from app.domains.credit.agents import CreditAgent
from app.domains.ecommerce.agents import ProductAgent
from app.domains.excelencia.agents import ExcelenciaAgent
from app.domains.healthcare.agents import HealthcareAgent
from app.orchestration import SuperOrchestrator

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer
    from app.core.container.credit import CreditContainer
    from app.core.container.ecommerce import EcommerceContainer
    from app.core.container.excelencia import ExcelenciaContainer
    from app.core.container.healthcare import HealthcareContainer

logger = logging.getLogger(__name__)


class AgentsContainer:
    """
    Agents container.

    Single Responsibility: Create domain agents and orchestrator.
    """

    def __init__(
        self,
        base: "BaseContainer",
        ecommerce: "EcommerceContainer",
        credit: "CreditContainer",
        healthcare: "HealthcareContainer",
        excelencia: "ExcelenciaContainer",
    ):
        """
        Initialize agents container.

        Args:
            base: BaseContainer with shared singletons
            ecommerce: EcommerceContainer for product agent dependencies
            credit: CreditContainer for credit agent dependencies
            healthcare: HealthcareContainer for healthcare agent dependencies
            excelencia: ExcelenciaContainer for excelencia agent dependencies
        """
        self._base = base
        self._ecommerce = ecommerce
        self._credit = credit
        self._healthcare = healthcare
        self._excelencia = excelencia

    # ==================== AGENTS ====================

    def create_product_agent(self) -> IAgent:
        """Create Product Agent with all dependencies."""
        agent_config = self._base.config.get("product_agent", {})

        logger.info("Creating ProductAgent")
        return ProductAgent(
            product_repository=self._ecommerce.create_product_repository(),
            vector_store=self._base.get_vector_store(),
            llm=self._base.get_llm(),
            config=agent_config,
        )

    def create_credit_agent(self) -> IAgent:
        """Create Credit Agent with all dependencies."""
        agent_config = self._base.config.get("credit_agent", {})

        logger.info("Creating CreditAgent")
        return CreditAgent(
            credit_account_repository=self._credit.create_credit_account_repository(),
            payment_repository=self._credit.create_payment_repository(),
            llm=self._base.get_llm(),
            config=agent_config,
        )

    def create_healthcare_agent(self) -> IAgent:
        """Create Healthcare Agent with all dependencies."""
        agent_config = self._base.config.get("healthcare_agent", {})

        logger.info("Creating HealthcareAgent")
        return HealthcareAgent(config=agent_config)

    def create_excelencia_agent(self) -> IAgent:
        """Create Excelencia Agent with all dependencies."""
        agent_config = self._base.config.get("excelencia_agent", {})

        logger.info("Creating ExcelenciaAgent")
        return ExcelenciaAgent(config=agent_config)

    # ==================== ORCHESTRATOR ====================

    def create_super_orchestrator(self) -> SuperOrchestrator:
        """Create Super Orchestrator with all domain agents."""
        orchestrator_config = self._base.config.get("orchestrator", {})

        # Create all domain agents
        domain_agents = {
            "ecommerce": self.create_product_agent(),
            "credit": self.create_credit_agent(),
            "healthcare": self.create_healthcare_agent(),
            "excelencia": self.create_excelencia_agent(),
        }

        logger.info(
            f"Creating SuperOrchestrator with {len(domain_agents)} domains: "
            f"{list(domain_agents.keys())}"
        )

        return SuperOrchestrator(
            domain_agents=domain_agents,
            llm=self._base.get_llm(),
            config=orchestrator_config,
        )
