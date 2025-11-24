"""
Product Agent for E-commerce Domain

Clean architecture agent that delegates to use cases.
Follows SOLID principles and implements IAgent interface.
"""

import logging
from typing import Any, Dict, Optional

from app.core.interfaces.agent import AgentType, IAgent
from app.core.interfaces.llm import ILLM
from app.core.interfaces.repository import ISearchableRepository
from app.core.interfaces.vector_store import IVectorStore
from app.domains.ecommerce.application.use_cases import (
    GetFeaturedProductsRequest,
    GetFeaturedProductsUseCase,
    GetProductsByCategoryRequest,
    GetProductsByCategoryUseCase,
    SearchProductsRequest,
    SearchProductsUseCase,
)

logger = logging.getLogger(__name__)


class ProductAgent(IAgent):
    """
    Product Agent following Clean Architecture.

    Single Responsibility: Coordinate product-related requests
    Dependency Inversion: Depends on use cases and interfaces
    Open/Closed: Easy to add new use cases without modifying agent
    """

    def __init__(
        self,
        product_repository: ISearchableRepository,
        vector_store: IVectorStore,
        llm: ILLM,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize agent with dependencies.

        Args:
            product_repository: Repository for product data access
            vector_store: Vector store for semantic search
            llm: Language model for query enhancement and response generation
            config: Optional configuration
        """
        self._config = config or {}
        self._product_repo = product_repository
        self._vector_store = vector_store
        self._llm = llm

        # Initialize use cases (dependency injection)
        self._search_use_case = SearchProductsUseCase(
            product_repository=product_repository,
            vector_store=vector_store,
            llm=llm,
        )
        self._category_use_case = GetProductsByCategoryUseCase(product_repository=product_repository)
        self._featured_use_case = GetFeaturedProductsUseCase(product_repository=product_repository)

        logger.info("ProductAgent initialized with use cases")

    @property
    def agent_type(self) -> AgentType:
        """Agent type identifier"""
        return AgentType.PRODUCT_SEARCH

    @property
    def agent_name(self) -> str:
        """Agent name"""
        return "product_agent"

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent logic.

        Args:
            state: Current conversation state

        Returns:
            Updated state
        """
        try:
            # Extract message
            messages = state.get("messages", [])
            if not messages:
                return self._error_response("No message provided", state)

            user_message = messages[-1].get("content", "")

            # Analyze intent
            intent = await self._analyze_intent(user_message)
            logger.info(f"Detected intent: {intent}")

            # Route to appropriate use case
            if intent == "search":
                response = await self._handle_search(user_message, state)
            elif intent == "category_browse":
                response = await self._handle_category_browse(user_message, state)
            elif intent == "featured":
                response = await self._handle_featured(state)
            else:
                response = await self._handle_search(user_message, state)  # Default

            return response

        except Exception as e:
            logger.error(f"Error in ProductAgent.execute: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def validate_input(self, state: Dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if valid, False otherwise
        """
        # Check for messages
        messages = state.get("messages", [])
        if not messages:
            return False

        # Check message has content
        last_message = messages[-1]
        if not last_message.get("content"):
            return False

        return True

    async def _analyze_intent(self, message: str) -> str:
        """
        Analyze user intent using LLM.

        Args:
            message: User message

        Returns:
            Intent string ('search', 'category_browse', 'featured', etc.)
        """
        try:
            prompt = f"""Analyze this product query and return ONLY the intent type:

Query: "{message}"

Intent types:
- search: General product search
- category_browse: Browsing a specific category
- featured: Asking for featured/highlighted products

Return ONLY one word: search, category_browse, or featured"""

            response = await self._llm.generate(prompt, temperature=0.2, max_tokens=10)
            intent = response.strip().lower()

            if intent in ["search", "category_browse", "featured"]:
                return intent

            return "search"  # Default

        except Exception as e:
            logger.warning(f"Error analyzing intent: {e}")
            return "search"

    async def _handle_search(self, message: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle product search request.

        Args:
            message: User message
            state: Current state

        Returns:
            Updated state
        """
        try:
            # Create use case request
            request = SearchProductsRequest(
                query=message,
                limit=self._config.get("max_results", 10),
                use_semantic_search=self._config.get("use_semantic_search", True),
            )

            # Execute use case
            response = await self._search_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Search failed", state)

            # Generate AI response
            ai_response = await self._generate_product_response(message, response.products, response.search_method)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "products": response.products,
                    "search_method": response.search_method,
                    "count": response.total_count,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in search handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _handle_category_browse(self, message: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle category browsing request.

        Args:
            message: User message
            state: Current state

        Returns:
            Updated state
        """
        try:
            # Extract category from message (simple extraction)
            category = await self._extract_category(message)

            if not category:
                # Fallback to search
                return await self._handle_search(message, state)

            # Create use case request
            request = GetProductsByCategoryRequest(
                category=category,
                limit=self._config.get("max_results", 50),
                sort_by="featured",
            )

            # Execute use case
            response = await self._category_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Category browse failed", state)

            # Generate AI response
            ai_response = await self._generate_category_response(category, response.products)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "products": response.products,
                    "category": category,
                    "count": response.total_count,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in category browse handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _handle_featured(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle featured products request.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        try:
            # Create use case request
            request = GetFeaturedProductsRequest(limit=self._config.get("max_featured", 10))

            # Execute use case
            response = await self._featured_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Featured query failed", state)

            # Generate AI response
            ai_response = await self._generate_featured_response(response.products)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "products": response.products,
                    "count": response.total_count,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in featured handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _generate_product_response(self, query: str, products: list, search_method: str) -> str:
        """Generate AI response for product search"""
        try:
            if not products:
                return f"No encontré productos para '{query}'. ¿Podrías ser más específico?"

            # Format products for context
            products_text = "\n".join(
                [f"{i+1}. {p['name']} - ${p['price']:,.2f} (Stock: {p['stock']})" for i, p in enumerate(products[:5])]
            )

            prompt = f"""Genera una respuesta amigable para esta búsqueda de productos:

Consulta: "{query}"
Método: {search_method}
Productos encontrados: {len(products)}

Productos principales:
{products_text}

Genera una respuesta:
- Amigable y profesional
- Destaca los productos más relevantes
- Menciona precios y disponibilidad
- Máximo 5 líneas
- Usa emojis apropiados pero sin exceso"""

            response = await self._llm.generate(prompt, temperature=0.7, max_tokens=200)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Encontré {len(products)} productos que podrían interesarte."

    async def _generate_category_response(self, category: str, products: list) -> str:
        """Generate AI response for category browse"""
        if not products:
            return f"No encontré productos en la categoría '{category}'."

        products_text = "\n".join([f"{i+1}. {p['name']} - ${p['price']:,.2f}" for i, p in enumerate(products[:5])])

        try:
            prompt = f"""Responde sobre productos de una categoría:

Categoría: {category}
Total productos: {len(products)}

Principales productos:
{products_text}

Genera respuesta breve y amigable (máximo 4 líneas)"""

            response = await self._llm.generate(prompt, temperature=0.7, max_tokens=150)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating category response: {e}")
            return f"Tenemos {len(products)} productos en {category}."

    async def _generate_featured_response(self, products: list) -> str:
        """Generate AI response for featured products"""
        if not products:
            return "No hay productos destacados en este momento."

        try:
            products_text = "\n".join([f"{i+1}. {p['name']} - ${p['price']:,.2f}" for i, p in enumerate(products[:5])])

            prompt = f"""Presenta productos destacados:

Total: {len(products)}

Productos:
{products_text}

Genera respuesta atractiva (máximo 4 líneas)"""

            response = await self._llm.generate(prompt, temperature=0.7, max_tokens=150)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating featured response: {e}")
            return f"Tenemos {len(products)} productos destacados disponibles."

    async def _extract_category(self, message: str) -> Optional[str]:
        """Extract category from message"""
        # Simple keyword extraction (could be enhanced with LLM)
        message_lower = message.lower()
        categories = [
            "computadoras",
            "notebooks",
            "monitores",
            "periféricos",
            "componentes",
        ]

        for category in categories:
            if category in message_lower:
                return category

        return None

    def _error_response(self, error: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Disculpa, tuve un problema. ¿Podrías reformular tu pregunta?",
                }
            ],
            "current_agent": self.agent_name,
            "error_count": state.get("error_count", 0) + 1,
            "error": error,
        }
