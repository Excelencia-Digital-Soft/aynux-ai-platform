"""
Database search strategy using PostgreSQL direct queries.

Implements traditional database search with filtering and text search.
"""

from typing import Any, Dict

from app.domains.ecommerce.agents.tools.product_tool import ProductTool

from ..models import SearchResult, UserIntent
from .base_strategy import BaseSearchStrategy


class DatabaseSearchStrategy(BaseSearchStrategy):
    """
    Search strategy using PostgreSQL database queries.

    Applies SOLID principles:
    - SRP: Focuses solely on database search operations
    - OCP: Extensible through configuration without modification
    - LSP: Fully substitutable with other search strategies
    - DIP: Depends on ProductTool abstraction
    """

    def __init__(self, product_tool: ProductTool, config: Dict[str, Any]):
        """
        Initialize database search strategy.

        Args:
            product_tool: ProductTool instance for database operations
            config: Strategy configuration including:
                - max_results: int (default 10)
                - require_stock: bool (default True)
        """
        super().__init__(config)
        self.product_tool = product_tool

        # Configuration with defaults
        self.max_results = config.get("max_results", 10)
        self.require_stock = config.get("require_stock", False)  # Changed to False to show all products
        self.priority = 50  # Lowest priority for SQL fallback

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "database"

    @property
    def name(self) -> str:
        """Return strategy name (alias for strategy_name)."""
        return self.strategy_name

    async def search(self, query: str, intent: UserIntent, max_results: int) -> SearchResult:
        """
        Execute database search with intent-based routing.

        Args:
            query: User's natural language query
            intent: Analyzed user intent with structured data
            max_results: Maximum number of products to return

        Returns:
            SearchResult with products and metadata
        """
        self._log_search_start(query, intent, max_results)

        try:
            # Route to appropriate search method based on intent
            search_result = await self._route_search(intent, max_results)

            if not search_result.get("success", False):
                error_msg = search_result.get("error", "Database search failed")
                return SearchResult(
                    success=False,
                    products=[],
                    source=self.strategy_name,
                    error=error_msg,
                )

            products = search_result.get("products", [])

            # Build result metadata
            result_metadata = {
                "query": query,
                "total_results": len(products),
                "intent": intent.intent,
                "action": intent.action_needed,
                "search_method": search_result.get("method", "unknown"),
            }

            result = SearchResult(
                success=True,
                products=products,
                source=self.strategy_name,
                metadata=result_metadata,
            )

            self._log_search_result(result)
            return result

        except Exception as e:
            self.logger.error(f"Database search failed: {str(e)}")
            return SearchResult(
                success=False,
                products=[],
                source=self.strategy_name,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """
        Check if database is operational.

        Returns:
            True if database can execute queries
        """
        try:
            # Test database with minimal query
            test_result = await self.product_tool("featured", limit=1)
            is_healthy = test_result.get("success", False)

            if is_healthy:
                self.logger.debug("Database health check passed")
            else:
                self.logger.warning("Database health check failed")

            return is_healthy

        except Exception as e:
            self.logger.warning(f"Database health check failed: {str(e)}")
            return False

    async def _route_search(self, intent: UserIntent, max_results: int) -> Dict[str, Any]:
        """
        Route search to appropriate database method based on intent.

        Args:
            intent: User intent with search parameters
            max_results: Maximum results to return

        Returns:
            Dict with search results from ProductTool
        """
        action = intent.action_needed

        # Priority 1: Featured products request
        if action == "show_featured" or intent.intent == "show_general_catalog":
            result = await self.product_tool("featured", limit=max_results)
            result["method"] = "featured"
            return result

        # Priority 2: Category search with fallback to text search
        if (action == "search_category" or intent.intent == "search_by_category") and intent.category:
            result = await self.product_tool("by_category", category=intent.category, limit=max_results)

            # If category search found no results, fallback to text search
            if not result.get("success") or len(result.get("products", [])) == 0:
                self.logger.info(f"Category '{intent.category}' not found, falling back to text search")
                result = await self.product_tool("search", search_term=intent.category, limit=max_results)
                result["method"] = "by_category_fallback_text"
            else:
                result["method"] = "by_category"

            return result

        # Priority 3: Brand search with fallback to text search
        if (action == "search_brand" or intent.intent == "search_by_brand") and intent.brand:
            result = await self.product_tool("by_brand", brand=intent.brand, limit=max_results)

            # If brand search found no results, fallback to text search
            if not result.get("success") or len(result.get("products", [])) == 0:
                self.logger.info(f"Brand '{intent.brand}' not found, falling back to text search")
                result = await self.product_tool("search", search_term=intent.brand, limit=max_results)
                result["method"] = "by_brand_fallback_text"
            else:
                result["method"] = "by_brand"

            return result

        # Priority 4: Price range search
        if (action == "search_price" or intent.intent == "search_by_price") and (intent.price_min or intent.price_max):
            result = await self.product_tool(
                "by_price_range",
                min_price=intent.price_min,
                max_price=intent.price_max,
                limit=max_results,
            )
            result["method"] = "by_price_range"
            return result

        # Priority 5: Specific product or text search
        if action == "search_products" or intent.intent in ["search_specific_products", "get_product_details"]:
            # Build comprehensive search term
            search_terms_list = []

            if intent.specific_product:
                search_terms_list.append(intent.specific_product)

            if intent.search_terms:
                search_terms_list.extend(intent.search_terms)

            if intent.category:
                search_terms_list.append(intent.category)

            if intent.brand:
                search_terms_list.append(intent.brand)

            if search_terms_list:
                search_term = " ".join(search_terms_list)
                result = await self.product_tool("search", search_term=search_term, limit=max_results)
                result["method"] = "search_combined_terms"
                return result

        # Special preferences
        if intent.wants_featured:
            result = await self.product_tool("featured", limit=max_results)
            result["method"] = "featured_preference"
            return result

        if intent.wants_sale:
            result = await self.product_tool("on_sale", limit=max_results)
            result["method"] = "on_sale"
            return result

        # Advanced search with all available parameters
        search_params = self._build_advanced_search_params(intent, max_results)
        if search_params:
            result = await self.product_tool("search", **search_params)
            result["method"] = "advanced_search"
            return result

        # Ultimate fallback: featured products
        result = await self.product_tool("featured", limit=max_results)
        result["method"] = "fallback_featured"
        return result

    def _build_advanced_search_params(self, intent: UserIntent, max_results: int) -> Dict[str, Any]:
        """
        Build advanced search parameters from intent.

        Args:
            intent: User intent with search criteria
            max_results: Maximum results to return

        Returns:
            Search parameters dictionary
        """
        params = {}

        # Text search
        if intent.search_terms:
            params["search_term"] = " ".join(intent.search_terms)

        # Category filter
        if intent.category:
            params["category"] = intent.category

        # Brand filter
        if intent.brand:
            params["brand"] = intent.brand

        # Price range
        if intent.price_min:
            params["min_price"] = intent.price_min
        if intent.price_max:
            params["max_price"] = intent.price_max

        # Stock filter
        if self.require_stock:
            params["in_stock"] = True

        # Limit
        params["limit"] = max_results

        return params if len(params) > 1 else {}  # Return only if has more than just limit
