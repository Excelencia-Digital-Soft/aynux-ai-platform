"""
Product Node - E-commerce domain node for product search and catalog.

SOLID-compliant node that delegates all logic to ProductAgentOrchestrator
following the Strategy Pattern.
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.integrations.llm import OllamaLLM
from app.integrations.vector_stores import PgVectorIntegration
from app.domains.ecommerce.agents.product.product_agent_orchestrator import ProductAgentOrchestrator
from app.domains.ecommerce.agents.product.response import AIResponseGenerator
from app.domains.ecommerce.agents.product.strategies import (
    DatabaseSearchStrategy,
    PgVectorSearchStrategy,
    SQLGenerationSearchStrategy,
)
from app.core.utils.tracing import trace_async_method
from app.config.settings import get_settings
from app.domains.ecommerce.agents.tools.product_tool import ProductTool

logger = logging.getLogger(__name__)


class ProductNode(BaseAgent):
    """
    E-commerce Product Node following SOLID principles.

    Single Responsibility: Adapter between BaseAgent interface and Orchestrator.
    Dependency Inversion: Depends on abstractions (orchestrator) not concrete classes.
    """

    def __init__(
        self,
        ollama=None,
        postgres=None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize product node.

        Args:
            ollama: Ollama integration instance
            postgres: PostgreSQL connection (for compatibility)
            config: Agent configuration
        """
        super().__init__("product_node", config or {}, ollama=ollama, postgres=postgres)

        settings = get_settings()
        self.ollama = ollama or OllamaLLM()
        self.postgres = postgres

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
            f"ProductNode initialized with "
            f"{len(search_strategies)} search strategies, "
            f"{len(response_generators)} response generators"
        )

    def _initialize_search_strategies(self, settings, config):
        """
        Initialize search strategies based on configuration.

        Follows Open/Closed Principle - new strategies can be added here.
        """
        strategies = []

        # pgvector strategy (highest priority - primary vector search)
        pgvector_integration = PgVectorIntegration(ollama=self.ollama)
        strategies.append(
            PgVectorSearchStrategy(
                pgvector=pgvector_integration,
                config=config,
            )
        )
        logger.info("pgvector search strategy enabled (priority: 10)")

        # SQL Generation strategy (medium-low priority, for complex queries)
        use_sql_generation = getattr(settings, "USE_SQL_GENERATION", True)
        if use_sql_generation:
            strategies.append(
                SQLGenerationSearchStrategy(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config=config,
                )
            )
            logger.info("SQL generation search strategy enabled (priority: 40)")

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
        """
        generators = []

        # AI response generator (highest priority)
        generators.append(
            AIResponseGenerator(
                ollama=self.ollama,
                config=config,
            )
        )

        return generators

    @trace_async_method(
        name="product_node_process",
        run_type="chain",
        metadata={"agent_type": "product_node", "domain": "ecommerce"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Process user message using orchestrator.

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
            logger.error(f"Error in product node: {e}", exc_info=True)

            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Disculpa, tuve un problema consultando los productos. "
                            "Podrias reformular tu pregunta?"
                        ),
                    }
                ],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def health_check(self) -> dict[str, Any]:
        """Check health of node and orchestrator."""
        try:
            orchestrator_health = await self.orchestrator.health_check()
            return {
                "node": "product_node",
                "healthy": orchestrator_health["healthy"],
                "orchestrator": orchestrator_health,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "node": "product_node",
                "healthy": False,
                "error": str(e),
            }

    def get_configuration(self) -> dict[str, Any]:
        """Get node configuration."""
        return {
            "node_name": self.name,
            "node_config": self.config,
            "orchestrator": self.orchestrator.get_configuration(),
        }


# Alias for backward compatibility
RefactoredProductAgent = ProductNode
ProductAgent = ProductNode
