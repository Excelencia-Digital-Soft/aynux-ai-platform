"""
Super Orchestrator - Multi-Domain Router

Routes conversations to appropriate domain agents based on context and intent.
Follows Clean Architecture and SOLID principles.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.agent import IAgent
from app.core.interfaces.llm import ILLM

logger = logging.getLogger(__name__)


class SuperOrchestrator:
    """
    Super Orchestrator for multi-domain routing.

    Single Responsibility: Route messages to appropriate domain agents
    Dependency Inversion: Depends on IAgent and ILLM interfaces
    Open/Closed: Easy to add new domains without modifying orchestrator
    """

    def __init__(
        self,
        domain_agents: Dict[str, IAgent],
        llm: ILLM,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Super Orchestrator.

        Args:
            domain_agents: Dictionary mapping domain names to agent instances
            llm: Language model for domain detection
            config: Optional configuration
        """
        self.domain_agents = domain_agents
        self.llm = llm
        self.config = config or {}

        # Default domain if detection fails
        self.default_domain = self.config.get("default_domain", "ecommerce")

        logger.info(
            f"SuperOrchestrator initialized with {len(domain_agents)} domains: "
            f"{list(domain_agents.keys())}"
        )

    async def route_message(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route message to appropriate domain agent.

        Args:
            state: Current conversation state

        Returns:
            Updated state from domain agent
        """
        try:
            # Extract message
            messages = state.get("messages", [])
            if not messages:
                return self._error_response("No message provided", state)

            current_message = messages[-1].get("content", "")

            # Detect domain
            domain = await self._detect_domain(current_message, state)
            logger.info(f"Detected domain: {domain}")

            # Get appropriate agent
            agent = self.domain_agents.get(domain)

            if not agent:
                logger.warning(f"Domain '{domain}' not found, using default: {self.default_domain}")
                agent = self.domain_agents.get(self.default_domain)

            if not agent:
                return self._error_response(f"No agent available for domain: {domain}", state)

            # Validate agent can handle this
            if not await agent.validate_input(state):
                logger.warning(f"Agent validation failed for domain: {domain}")
                return self._error_response("Invalid input for domain agent", state)

            # Execute agent
            logger.info(f"Routing to {agent.agent_name} (domain: {domain})")
            result = await agent.execute(state)

            # Add routing metadata
            result["routing"] = {
                "detected_domain": domain,
                "agent_used": agent.agent_name,
                "orchestrator": "super_orchestrator",
            }

            return result

        except Exception as e:
            logger.error(f"Error in SuperOrchestrator: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _detect_domain(
        self, message: str, state: Dict[str, Any]
    ) -> str:
        """
        Detect domain from message using LLM.

        Args:
            message: User message
            state: Current state (for context)

        Returns:
            Domain name
        """
        try:
            # Check if domain is explicitly set in state
            explicit_domain = state.get("domain")
            if explicit_domain and explicit_domain in self.domain_agents:
                logger.info(f"Using explicit domain from state: {explicit_domain}")
                return explicit_domain

            # Use LLM to detect domain
            available_domains = list(self.domain_agents.keys())
            domains_list = ", ".join(available_domains)

            prompt = f"""Analyze this user message and determine which business domain it belongs to.

Message: "{message}"

Available domains:
- ecommerce: Products, shopping, orders, promotions, inventory
- credit: Credit accounts, payments, balances, collections, loans
- healthcare: Patients, appointments, medical records, prescriptions
- excelencia: Company services, quotes, portfolio, contact sales

Return ONLY the domain name (one word): {domains_list}

If unclear, return: {self.default_domain}"""

            response = await self.llm.generate(
                prompt,
                temperature=0.2,
                max_tokens=10
            )

            detected_domain = response.strip().lower()

            # Validate detected domain
            if detected_domain not in available_domains:
                logger.warning(
                    f"LLM returned invalid domain '{detected_domain}', "
                    f"using default: {self.default_domain}"
                )
                return self.default_domain

            return detected_domain

        except Exception as e:
            logger.error(f"Error detecting domain: {e}", exc_info=True)
            return self.default_domain

    async def get_available_domains(self) -> List[Dict[str, str]]:
        """
        Get list of available domains.

        Returns:
            List of domain information
        """
        domains = []
        for domain_name, agent in self.domain_agents.items():
            domains.append({
                "name": domain_name,
                "agent_type": agent.agent_type.value if hasattr(agent.agent_type, "value") else str(agent.agent_type),
                "agent_name": agent.agent_name,
            })
        return domains

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all domain agents.

        Returns:
            Health status for each domain
        """
        health = {
            "orchestrator": "healthy",
            "domains": {},
        }

        for domain_name, agent in self.domain_agents.items():
            try:
                # If agent has health_check method, use it
                if hasattr(agent, "health_check"):
                    agent_health = await agent.health_check()
                    health["domains"][domain_name] = agent_health
                else:
                    health["domains"][domain_name] = {
                        "status": "available",
                        "agent": agent.agent_name,
                    }
            except Exception as e:
                logger.error(f"Health check failed for {domain_name}: {e}")
                health["domains"][domain_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return health

    def _error_response(self, error: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate error response.

        Args:
            error: Error message
            state: Current state

        Returns:
            Error response dict
        """
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Disculpa, tuve un problema procesando tu solicitud. ¿Podrías intentar de nuevo?",
                }
            ],
            "error": error,
            "error_count": state.get("error_count", 0) + 1,
            "routing": {
                "status": "failed",
                "error": error,
            },
        }

    def register_domain(self, domain_name: str, agent: IAgent) -> None:
        """
        Register a new domain agent.

        Args:
            domain_name: Name of the domain
            agent: Agent instance implementing IAgent
        """
        if domain_name in self.domain_agents:
            logger.warning(f"Overwriting existing domain: {domain_name}")

        self.domain_agents[domain_name] = agent
        logger.info(f"Registered domain '{domain_name}' with agent: {agent.agent_name}")

    def unregister_domain(self, domain_name: str) -> bool:
        """
        Unregister a domain agent.

        Args:
            domain_name: Name of the domain to remove

        Returns:
            True if removed, False if not found
        """
        if domain_name in self.domain_agents:
            del self.domain_agents[domain_name]
            logger.info(f"Unregistered domain: {domain_name}")
            return True

        logger.warning(f"Domain not found for unregistration: {domain_name}")
        return False
