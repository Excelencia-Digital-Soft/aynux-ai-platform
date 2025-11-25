"""
Product Agent Orchestrator

Orchestrates product search and response generation using Strategy Pattern.
Follows SOLID principles for maintainability and extensibility.
"""

import logging
from typing import Any, Dict, List, Optional

from app.agents.integrations.ollama_integration import OllamaIntegration
from app.agents.product.intent_analyzer import IntentAnalyzer

from .response import (
    BaseResponseGenerator,
    GeneratedResponse,
    ResponseContext,
)
from .strategies import BaseSearchStrategy, SearchResult

logger = logging.getLogger(__name__)


class ProductAgentOrchestrator:
    """
    Orchestrates product search and response generation.

    Follows:
    - Single Responsibility: Coordinate strategies only
    - Open/Closed: Add new strategies without modifying orchestrator
    - Dependency Inversion: Depends on abstractions (BaseSearchStrategy, BaseResponseGenerator)
    - Interface Segregation: Small, focused interfaces
    """

    def __init__(
        self,
        search_strategies: List[BaseSearchStrategy],
        response_generators: List[BaseResponseGenerator],
        intent_analyzer: Optional[IntentAnalyzer] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize orchestrator with strategies.

        Args:
            search_strategies: List of search strategies (ordered by priority)
            response_generators: List of response generators (ordered by priority)
            intent_analyzer: Intent analysis service
            config: Configuration dict
        """
        self.config = config or {}

        # Sort strategies by priority (lower = higher priority)
        self.search_strategies = sorted(search_strategies, key=lambda s: s.priority)
        self.response_generators = sorted(response_generators, key=lambda g: g.priority)

        # Intent analyzer
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(ollama=OllamaIntegration(), temperature=0.3)

        # Configuration
        self.min_results_threshold = self.config.get("min_results_threshold", 2)

        logger.info(
            f"ProductAgentOrchestrator initialized with "
            f"{len(self.search_strategies)} search strategies, "
            f"{len(self.response_generators)} response generators"
        )

    async def process_query(
        self,
        user_query: str,
        conversation_state: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Process user query and generate response.

        Main orchestration flow:
        1. Analyze user intent
        2. Execute search strategies (with fallback)
        3. Generate response
        4. Return result

        Args:
            user_query: User's query text
            conversation_state: Current conversation state
            limit: Maximum products to return

        Returns:
            Dict with response text, products, and metadata
        """
        try:
            # Step 1: Analyze user intent
            intent_result = await self.intent_analyzer.analyze_intent(user_query)

            logger.info(
                f"Intent analysis: {intent_result.intent} "
                f"(confidence: {intent_result.confidence:.2f}, "
                f"action: {intent_result.action_needed})"
            )

            # Step 2: Execute search with fallback
            search_result = await self._execute_search_with_fallback(user_query, intent_result, limit)

            # Step 3: Generate response
            response = await self._generate_response(search_result, user_query, intent_result, conversation_state)

            # Step 4: Build result
            return {
                "response_text": response.text,
                "products": search_result.products,
                "source": search_result.source,
                "intent": intent_result.to_dict(),
                "response_type": response.response_type,
                "metadata": {
                    "search": search_result.metadata,
                    "response": response.metadata,
                },
            }

        except Exception as e:
            logger.error(f"Error in orchestrator process_query: {e}", exc_info=True)
            return self._generate_error_response(user_query, str(e))

    async def _execute_search_with_fallback(
        self,
        user_query: str,
        intent_result: Any,
        limit: int,
    ) -> SearchResult:
        """
        Execute search strategies with automatic fallback.

        Tries strategies in priority order until sufficient results found.

        Args:
            user_query: User query
            intent_result: Intent analysis result (UserIntent object)
            limit: Result limit

        Returns:
            SearchResult from first successful strategy
        """
        last_error = None

        for strategy in self.search_strategies:
            try:
                # Check if strategy can handle this intent
                if not await strategy.can_handle(intent_result):
                    logger.debug(f"Strategy {strategy.name} cannot handle intent, skipping")
                    continue

                # Check strategy health
                if not await strategy.health_check():
                    logger.warning(f"Strategy {strategy.name} health check failed, skipping")
                    continue

                # Execute search
                logger.info(f"Attempting search with strategy: {strategy.name}")
                result = await strategy.search(user_query, intent_result, limit)

                # Check if results are sufficient
                if result.success and len(result.products) >= self.min_results_threshold:
                    logger.info(f"Strategy {strategy.name} returned {len(result.products)} products")
                    return result

                # Not enough results, try next strategy
                logger.info(
                    f"Strategy {strategy.name} returned insufficient results "
                    f"({len(result.products)} < {self.min_results_threshold}), "
                    f"trying next strategy"
                )

            except Exception as e:
                last_error = e
                logger.error(f"Error in search strategy {strategy.name}: {e}", exc_info=True)
                continue

        # All strategies failed or returned insufficient results
        logger.warning("All search strategies failed or returned insufficient results")
        return SearchResult(
            products=[],
            source="none",
            query=user_query,
            success=False,
            error=str(last_error) if last_error else "No results found",
        )

    async def _generate_response(
        self,
        search_result: SearchResult,
        user_query: str,
        intent_result: Any,
        conversation_state: Optional[Dict[str, Any]],
    ) -> GeneratedResponse:
        """
        Generate response using available generators.

        Tries generators in priority order until one succeeds.

        Args:
            search_result: Search result
            user_query: User query
            intent_result: Intent analysis (UserIntent object)
            conversation_state: Conversation state

        Returns:
            GeneratedResponse
        """
        # Build response context
        context = ResponseContext(
            products=search_result.products,
            user_query=user_query,
            intent_analysis=intent_result.to_dict(),
            search_metadata=search_result.metadata,
            conversation_state=conversation_state or {},
        )

        # Try generators in priority order
        for generator in self.response_generators:
            try:
                # Check if generator can handle context
                if not await generator.can_generate(context):
                    logger.debug(f"Generator {generator.name} cannot handle context, skipping")
                    continue

                # Check generator health
                if not await generator.health_check():
                    logger.warning(f"Generator {generator.name} health check failed, skipping")
                    continue

                # Generate response
                logger.info(f"Generating response with: {generator.name}")
                response = await generator.generate(context)

                return response

            except Exception as e:
                logger.error(f"Error in response generator {generator.name}: {e}", exc_info=True)
                continue

        # All generators failed - create basic fallback
        logger.error("All response generators failed, using basic fallback")
        return self._create_basic_fallback_response(search_result, user_query)

    def _create_basic_fallback_response(self, search_result: SearchResult, _user_query: str) -> GeneratedResponse:
        """
        Create basic fallback response when all generators fail.

        Args:
            search_result: Search result
            user_query: User query

        Returns:
            Basic fallback response
        """
        if search_result.products:
            text = (
                f"Encontré {len(search_result.products)} productos. "
                "Por favor, intenta reformular tu consulta para más detalles."
            )
        else:
            text = "No encontré productos. ¿Podrías intentar con otros términos de búsqueda?"

        return GeneratedResponse(
            text=text,
            response_type="basic_fallback",
            metadata={"reason": "all_generators_failed"},
            requires_followup=True,
        )

    def _generate_error_response(self, user_query: str, error: str) -> Dict[str, Any]:
        """
        Generate error response when orchestration fails.

        Args:
            user_query: User query
            error: Error message

        Returns:
            Error response dict
        """
        return {
            "response_text": ("Disculpa, tuve un problema procesando tu consulta. ¿Podrías reformular tu pregunta?"),
            "products": [],
            "source": "error",
            "intent": {"intent": "unknown", "error": error},
            "response_type": "error",
            "metadata": {"error": error, "query": user_query},
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all strategies and generators.

        Returns:
            Health status dict
        """
        health: Dict[str, Any] = {
            "healthy": True,
            "search_strategies": {},
            "response_generators": {},
        }

        # Check search strategies
        for strategy in self.search_strategies:
            try:
                is_healthy = await strategy.health_check()
                health["search_strategies"][strategy.name] = {
                    "healthy": is_healthy,
                    "priority": strategy.priority,
                }
                if not is_healthy:
                    health["healthy"] = False
            except Exception as e:
                health["search_strategies"][strategy.name] = {
                    "healthy": False,
                    "error": str(e),
                }
                health["healthy"] = False

        # Check response generators
        for generator in self.response_generators:
            try:
                is_healthy = await generator.health_check()
                health["response_generators"][generator.name] = {
                    "healthy": is_healthy,
                    "priority": generator.priority,
                }
                if not is_healthy:
                    health["healthy"] = False
            except Exception as e:
                health["response_generators"][generator.name] = {
                    "healthy": False,
                    "error": str(e),
                }
                health["healthy"] = False

        return health

    def get_configuration(self) -> Dict[str, Any]:
        """
        Get orchestrator configuration.

        Returns:
            Configuration dict
        """
        return {
            "search_strategies": [{"name": s.name, "priority": s.priority} for s in self.search_strategies],
            "response_generators": [{"name": g.name, "priority": g.priority} for g in self.response_generators],
            "min_results_threshold": self.min_results_threshold,
            "config": self.config,
        }
