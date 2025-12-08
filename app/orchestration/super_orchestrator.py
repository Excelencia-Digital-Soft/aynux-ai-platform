# ============================================================================
# SCOPE: GLOBAL
# Description: Orquestador principal que rutea mensajes a agentes de dominio.
#              Singleton creado una vez, compartido por todos los tenants.
# Tenant-Aware: No directamente - los agentes que usa pueden ser tenant-aware
#              via apply_tenant_config() si se activa el modo multi-tenant.
# ============================================================================
"""
Super Orchestrator - Multi-Domain Router

Routes conversations to appropriate domain agents based on context and intent.
Follows Clean Architecture and SOLID principles.
Uses centralized YAML-based prompt management.
"""

import inspect
import logging
from typing import Any, Dict, List, Optional

from app.core.interfaces.agent import IAgent
from app.core.interfaces.llm import ILLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

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

        # Initialize prompt manager for centralized prompt handling
        self._prompt_manager = PromptManager()

        # Default domain if detection fails
        self.default_domain = self.config.get("default_domain", "ecommerce")

        logger.info(
            f"SuperOrchestrator initialized with {len(domain_agents)} domains: "
            f"{list(domain_agents.keys())} and prompt manager"
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
                return await self._error_response("No message provided", state)

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
                return await self._error_response(f"No agent available for domain: {domain}", state)

            # Validate agent can handle this
            if not await agent.validate_input(state):
                logger.warning(f"Agent validation failed for domain: {domain}")
                return await self._error_response("Invalid input for domain agent", state)

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
            return await self._error_response(str(e), state)

    async def _detect_domain(self, message: str, state: Dict[str, Any]) -> str:
        """
        Detect domain from message using LLM with centralized prompt management.

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

            # Load prompt from YAML
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.ORCHESTRATOR_DOMAIN_DETECTION,
                variables={
                    "message": message,
                    "domains": domains_list,
                    "default_domain": self.default_domain,
                },
            )

            # Get metadata for LLM configuration
            template = await self._prompt_manager.get_template(
                PromptRegistry.ORCHESTRATOR_DOMAIN_DETECTION
            )
            temperature = (
                template.metadata.get("temperature", 0.2)
                if template and template.metadata
                else 0.2
            )
            max_tokens = (
                template.metadata.get("max_tokens", 10)
                if template and template.metadata
                else 10
            )

            response = await self.llm.generate(
                prompt, temperature=temperature, max_tokens=max_tokens
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
            domains.append(
                {
                    "name": domain_name,
                    "agent_type": (
                        agent.agent_type.value if hasattr(agent.agent_type, "value") else str(agent.agent_type)
                    ),
                    "agent_name": agent.agent_name,
                }
            )
        return domains

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all domain agents.

        Returns:
            Health status for each domain
        """
        health: Dict[str, Any] = {
            "orchestrator": "healthy",
            "domains": {},
        }

        for domain_name, agent in self.domain_agents.items():
            try:
                # If agent has health_check method, use it
                health_check_method = getattr(agent, "health_check", None)
                if health_check_method and callable(health_check_method):
                    # Check if it's a coroutine function
                    if inspect.iscoroutinefunction(health_check_method):
                        agent_health = await health_check_method()
                    else:
                        agent_health = health_check_method()
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

    async def _error_response(self, error: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate error response using YAML prompt.

        Args:
            error: Error message
            state: Current state

        Returns:
            Error response dict
        """
        try:
            error_message = await self._prompt_manager.get_prompt(
                PromptRegistry.ORCHESTRATOR_ERROR_RESPONSE,
            )
        except Exception as e:
            logger.warning(f"Failed to load error prompt from YAML: {e}")
            error_message = (
                "Disculpa, tuve un problema procesando tu solicitud. "
                "¿Podrías intentar de nuevo?"
            )

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": error_message.strip(),
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
