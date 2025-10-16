"""
Refactored Product Agent

SOLID-compliant replacement for the monolithic ProductAgent.
Delegates all logic to ProductAgentOrchestrator following the Strategy Pattern.

This agent is a thin wrapper that:
- Maintains compatibility with AgentFactory
- Inherits from BaseAgent
- Delegates to orchestrator (Dependency Inversion)
- Contains < 200 lines (vs 1,163 lines in original)
"""

import logging
from typing import Any, Dict, Optional

from app.config.settings import get_settings
from app.agents.integrations.ollama_integration import OllamaIntegration

from ..product.product_agent_orchestrator import ProductAgentOrchestrator
from ..product.response import AIResponseGenerator
from ..product.strategies import (
    PgVectorSearchStrategy,
    ChromaDBSearchStrategy,
    DatabaseSearchStrategy,
)
from ..integrations.pgvector_integration import PgVectorIntegration
from ..integrations.chroma_integration import ChromaDBIntegration
from ..tools.product_tool import ProductTool
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class RefactoredProductAgent(BaseAgent):
    """
    Refactored Product Agent following SOLID principles.

    Single Responsibility: Adapter between BaseAgent interface and Orchestrator.
    Dependency Inversion: Depends on abstractions (orchestrator) not concrete classes.
    """

    def __init__(
        self,
        ollama=None,
        postgres=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize refactored product agent.

        Args:
            ollama: Ollama integration instance
            postgres: PostgreSQL connection (for compatibility)
            config: Agent configuration
        """
        super().__init__("refactored_product_agent", config or {}, ollama=ollama, postgres=postgres)

        settings = get_settings()
        self.ollama = ollama or OllamaIntegration()
        self.postgres = postgres  # Store postgres for database strategy

        # Extract configuration
        agent_config = {
            "max_products_shown": self.config.get("max_products_shown", 10),
            "show_stock": self.config.get("show_stock", True),
            "show_prices": self.config.get("show_prices", True),
            "enable_recommendations": self.config.get("enable_recommendations", True),
            "temperature": self.config.get("temperature", 0.7),
            "min_results_threshold": self.config.get("min_results_threshold", 2),
        }

        # Initialize search strategies based on settings
        search_strategies = self._initialize_search_strategies(settings, agent_config)

        # Initialize response generators
        response_generators = self._initialize_response_generators(agent_config)

        # Create orchestrator with dependency injection
        self.orchestrator = ProductAgentOrchestrator(
            search_strategies=search_strategies,
            response_generators=response_generators,
            config=agent_config,
        )

        logger.info(
            f"RefactoredProductAgent initialized with "
            f"{len(search_strategies)} search strategies, "
            f"{len(response_generators)} response generators"
        )

    def _initialize_search_strategies(self, settings, config):
        """
        Initialize search strategies based on configuration.

        Follows Open/Closed Principle - new strategies can be added here.

        Args:
            settings: Application settings
            config: Agent configuration

        Returns:
            List of search strategy instances
        """
        strategies = []

        # pgvector strategy (highest priority if enabled)
        use_pgvector = getattr(settings, "USE_PGVECTOR", True)
        if use_pgvector:
            pgvector_integration = PgVectorIntegration(ollama=self.ollama)
            strategies.append(
                PgVectorSearchStrategy(
                    pgvector=pgvector_integration,
                    config=config,
                )
            )
            logger.info("pgvector search strategy enabled (priority: 10)")

        # ChromaDB strategy (medium priority, fallback)
        chroma_integration = ChromaDBIntegration()
        strategies.append(
            ChromaDBSearchStrategy(
                chroma=chroma_integration,
                collection_name="products",  # Default collection name
                config=config,
            )
        )
        logger.info("ChromaDB search strategy enabled (priority: 30)")

        # Database strategy (lowest priority, ultimate fallback)
        product_tool = ProductTool()
        strategies.append(
            DatabaseSearchStrategy(
                product_tool=product_tool,
                config=config,
            )
        )
        logger.info("Database search strategy enabled (priority: 50)")

        return strategies

    def _initialize_response_generators(self, config):
        """
        Initialize response generators.

        Follows Open/Closed Principle - new generators can be added here.

        Args:
            config: Agent configuration

        Returns:
            List of response generator instances
        """
        generators = []

        # AI response generator (highest priority)
        generators.append(
            AIResponseGenerator(
                ollama=self.ollama,
                config=config,
            )
        )

        # Add more generators here (e.g., CatalogResponseGenerator, FallbackGenerator)

        return generators

    @trace_async_method(
        name="refactored_product_agent_process",
        run_type="chain",
        metadata={"agent_type": "refactored_product", "uses_orchestrator": True},
        extract_state=True,
    )
    async def _process_internal(
        self, message: str, state_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process user message using orchestrator.

        This is the only method that contains business logic - delegating to orchestrator.

        Args:
            message: User message
            state_dict: Current conversation state

        Returns:
            State updates dict
        """
        try:
            # Get configuration
            limit = self.config.get("max_products_shown", 10)

            # Delegate to orchestrator
            result = await self.orchestrator.process_query(
                user_query=message,
                conversation_state=state_dict,
                limit=limit,
            )

            # Transform orchestrator result to agent state format
            return {
                "messages": [{"role": "assistant", "content": result["response_text"]}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "products": result["products"],
                    "intent": result["intent"],
                    "source": result["source"],
                    "response_type": result["response_type"],
                    "metadata": result["metadata"],
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in refactored product agent: {e}", exc_info=True)

            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Disculpa, tuve un problema consultando los productos. "
                            "¿Podrías reformular tu pregunta?"
                        ),
                    }
                ],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of agent and orchestrator.

        Returns:
            Health status dict
        """
        try:
            orchestrator_health = await self.orchestrator.health_check()
            return {
                "agent": "refactored_product_agent",
                "healthy": orchestrator_health["healthy"],
                "orchestrator": orchestrator_health,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "agent": "refactored_product_agent",
                "healthy": False,
                "error": str(e),
            }

    def get_configuration(self) -> Dict[str, Any]:
        """
        Get agent configuration.

        Returns:
            Configuration dict including orchestrator config
        """
        return {
            "agent_name": self.name,
            "agent_config": self.config,
            "orchestrator": self.orchestrator.get_configuration(),
        }


# Alias for backward compatibility
ProductAgent = RefactoredProductAgent
