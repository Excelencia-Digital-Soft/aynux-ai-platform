"""
WhatsApp Catalog Service - Specialized service for catalog operations
Following SOLID principles: Single Responsibility, Open/Closed, Dependency Inversion
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import get_settings
from app.integrations.whatsapp.messenger import WhatsAppMessenger
from app.models.whatsapp_advanced import (
    WhatsAppApiResponse,
)

logger = logging.getLogger(__name__)


class ICatalogRepository(ABC):
    """Interface for catalog data access (Interface Segregation Principle)"""

    @abstractmethod
    async def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get products by category from local database"""
        pass

    @abstractmethod
    async def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products by text query in local database"""
        pass

    @abstractmethod
    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get specific product by ID from local database"""
        pass


class ICatalogDecisionEngine(ABC):
    """Interface for catalog decision making (Interface Segregation Principle)"""

    @abstractmethod
    async def should_show_catalog(
        self, user_message: str, intent_analysis: Dict[str, Any], available_products: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Decide whether to show catalog or text response

        Returns:
            Tuple[bool, str]: (should_show_catalog, reason)
        """
        pass

    @abstractmethod
    async def select_catalog_products(
        self, products: List[Dict[str, Any]], user_intent: Dict[str, Any], max_products: int = 10
    ) -> List[Dict[str, Any]]:
        """Select and rank products for catalog display"""
        pass


class WhatsAppCatalogService:
    """
    Specialized service for WhatsApp Business Catalog operations
    Following Single Responsibility Principle
    """

    def __init__(
        self,
        whatsapp_service: Optional[WhatsAppMessenger] = None,
        catalog_repository: Optional[ICatalogRepository] = None,
        decision_engine: Optional[ICatalogDecisionEngine] = None,
    ):
        """
        Initialize with dependency injection (Dependency Inversion Principle)

        Args:
            whatsapp_service: WhatsApp messenger for API calls
            catalog_repository: Repository for product data access
            decision_engine: Engine for catalog display decisions
        """
        self.settings = get_settings()
        self.whatsapp_service = whatsapp_service or WhatsAppMessenger()
        self.catalog_repository = catalog_repository
        self.decision_engine = decision_engine

        # Configuration
        self.max_products_per_message = 10
        self.min_products_for_catalog = 2
        self.catalog_fallback_enabled = True

        logger.info("WhatsApp Catalog Service initialized")

    async def send_smart_product_response(
        self, user_phone: str, user_message: str, intent_analysis: Dict[str, Any], local_products: List[Dict[str, Any]]
    ) -> WhatsAppApiResponse:
        """
        Send intelligent product response: catalog or text based on context

        Args:
            user_phone: User's phone number
            user_message: Original user message
            intent_analysis: AI analysis of user intent
            local_products: Products found in local database

        Returns:
            WhatsAppApiResponse with result
        """
        try:
            # Decision: catalog vs text response
            should_use_catalog, reason = await self._should_show_catalog_display(
                user_message, intent_analysis, local_products
            )

            logger.info(f"Catalog decision: {should_use_catalog}, reason: {reason}")

            if should_use_catalog:
                return await self._send_catalog_response(user_phone, user_message, intent_analysis, local_products)
            else:
                # Fallback to text response (handled by ProductAgent)
                return WhatsAppApiResponse(
                    success=False,
                    error=f"Catalog not suitable: {reason}",
                    data={"fallback_to_text": True, "reason": reason},
                )

        except Exception as e:
            error_msg = f"Error in smart product response: {str(e)}"
            logger.error(error_msg)
            return WhatsAppApiResponse(success=False, error=error_msg, data={"fallback_to_text": True})

    async def _should_show_catalog_display(
        self, user_message: str, intent_analysis: Dict[str, Any], local_products: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Smart decision engine for catalog display

        Returns:
            Tuple[bool, str]: (should_show, reason)
        """
        # Use injected decision engine if available
        if self.decision_engine:
            return await self.decision_engine.should_show_catalog(user_message, intent_analysis, local_products)

        # Default decision logic

        # Check minimum product count
        if len(local_products) < self.min_products_for_catalog:
            return False, f"Insufficient products ({len(local_products)} < {self.min_products_for_catalog})"

        # Check if products have required fields for catalog
        catalog_ready_products = [p for p in local_products if self._is_product_catalog_ready(p)]

        if len(catalog_ready_products) < self.min_products_for_catalog:
            return False, f"Products missing catalog fields (only {len(catalog_ready_products)} ready)"

        # Check intent compatibility
        intent_type = intent_analysis.get("intent_type", "").lower()

        # Catalog-friendly intents
        catalog_friendly_intents = [
            "product_search",
            "category_browse",
            "product_list",
            "shopping",
            "browse",
            "ver productos",
            "mostrar productos",
        ]

        if any(intent in intent_type for intent in catalog_friendly_intents):
            return True, f"Intent '{intent_type}' is catalog-friendly"

        # Check for product browsing keywords
        browsing_keywords = [
            "ver",
            "mostrar",
            "catálogo",
            "productos",
            "opciones",
            "show",
            "catalog",
            "browse",
            "options",
            "list",
        ]

        message_lower = user_message.lower()
        if any(keyword in message_lower for keyword in browsing_keywords):
            return True, "Message contains browsing keywords"

        # Default to catalog if we have good products
        if len(catalog_ready_products) >= 5:
            return True, f"Good product availability ({len(catalog_ready_products)} products)"

        return False, "No strong indicators for catalog display"

    def _is_product_catalog_ready(self, product: Dict[str, Any]) -> bool:
        """Check if product has minimum fields for catalog display"""
        required_fields = ["id", "name"]
        recommended_fields = ["description", "price"]

        # Must have required fields
        if not all(field in product and product[field] for field in required_fields):
            return False

        # Should have at least one recommended field
        has_recommended = any(field in product and product[field] for field in recommended_fields)

        return has_recommended

    async def _send_catalog_response(
        self, user_phone: str, user_message: str, intent_analysis: Dict[str, Any], local_products: List[Dict[str, Any]]
    ) -> WhatsAppApiResponse:
        """Send catalog product list response"""
        try:
            # Select best products for catalog
            selected_products = await self._select_catalog_products(local_products, intent_analysis)

            if not selected_products:
                return WhatsAppApiResponse(
                    success=False, error="No suitable products for catalog display", data={"fallback_to_text": True}
                )

            # Generate catalog message text
            body_text = self._generate_catalog_body_text(intent_analysis, len(selected_products))

            header_text = self._generate_catalog_header_text(intent_analysis)

            # Highlight specific product if single product focus
            product_retailer_id = None
            if len(selected_products) == 1:
                product_retailer_id = selected_products[0].get("id")

            # Send catalog via WhatsApp
            response = await self.whatsapp_service.send_product_list(
                numero=user_phone, body_text=body_text, header_text=header_text, product_retailer_id=product_retailer_id
            )

            # Log successful catalog send
            if response.success:
                logger.info(f"Catalog sent successfully to {user_phone}: {len(selected_products)} products")

            return response

        except Exception as e:
            error_msg = f"Error sending catalog response: {str(e)}"
            logger.error(error_msg)
            return WhatsAppApiResponse(success=False, error=error_msg, data={"fallback_to_text": True})

    async def _select_catalog_products(
        self, products: List[Dict[str, Any]], intent_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Select and rank products for catalog display"""

        # Use injected decision engine if available
        if self.decision_engine:
            return await self.decision_engine.select_catalog_products(
                products, intent_analysis, self.max_products_per_message
            )

        # Default selection logic
        catalog_ready = [p for p in products if self._is_product_catalog_ready(p)]

        # Sort by relevance (price available first, then by name)
        catalog_ready.sort(
            key=lambda p: (
                0 if p.get("price") else 1,  # Products with price first
                p.get("name", "").lower(),
            )
        )

        return catalog_ready[: self.max_products_per_message]

    def _generate_catalog_body_text(self, intent_analysis: Dict[str, Any], product_count: int) -> str:
        """Generate appropriate body text for catalog message"""

        intent_type = intent_analysis.get("intent_type", "").lower()
        category = intent_analysis.get("category", "")

        if "category" in intent_type and category:
            return f"Aquí tienes nuestros productos de {category} ({product_count} disponibles):"
        elif "search" in intent_type:
            return f"Encontré {product_count} productos que podrían interesarte:"
        else:
            return f"Te muestro {product_count} productos de nuestro catálogo:"

    def _generate_catalog_header_text(self, intent_analysis: Dict[str, Any]) -> Optional[str]:
        """Generate optional header text for catalog message"""

        intent_type = intent_analysis.get("intent_type", "").lower()

        if "category" in intent_type:
            return "📱 Nuestro Catálogo"
        elif "search" in intent_type:
            return "🔍 Resultados de búsqueda"
        else:
            return "🛍️ Productos disponibles"

    async def get_catalog_info(self) -> Dict[str, Any]:
        """Get catalog configuration and status information"""
        try:
            config = self.whatsapp_service.get_catalog_configuration()

            # Test catalog API access
            products_response = await self.whatsapp_service.get_catalog_products(limit=1)

            return {
                "catalog_configured": True,
                "catalog_id": config.catalog_id,
                "catalog_accessible": products_response.success,
                "api_error": products_response.error if not products_response.success else None,
                "service_config": {
                    "max_products_per_message": self.max_products_per_message,
                    "min_products_for_catalog": self.min_products_for_catalog,
                    "fallback_enabled": self.catalog_fallback_enabled,
                },
            }

        except Exception as e:
            logger.error(f"Error getting catalog info: {str(e)}")
            return {"catalog_configured": False, "error": str(e)}

    async def sync_local_products_to_catalog(
        self, local_products: List[Dict[str, Any]], dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Sync local database products to WhatsApp Business Catalog
        (Future enhancement - requires Catalog Management API)

        Args:
            local_products: Products from local database
            dry_run: If True, only validate without making changes

        Returns:
            Sync results and statistics
        """
        logger.info(f"Catalog sync requested: {len(local_products)} products, dry_run={dry_run}")

        # For now, just return analysis
        catalog_ready = [p for p in local_products if self._is_product_catalog_ready(p)]

        return {
            "total_products": len(local_products),
            "catalog_ready": len(catalog_ready),
            "sync_needed": len(local_products) - len(catalog_ready),
            "dry_run": dry_run,
            "status": "analysis_only",
            "message": "Catalog Management API integration required for actual sync",
        }


# Default implementations for dependency injection


class DefaultCatalogRepository(ICatalogRepository):
    """Default implementation using ProductTool (can be replaced)"""

    def __init__(self):
        # Import here to avoid circular dependency
        from app.core.tools import ProductTool

        self.product_tool = ProductTool()

    async def get_products_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get products by category from local database"""
        try:
            result = await self.product_tool.get_products_by_category(category, limit=limit)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Error getting products by category: {str(e)}")
            return []

    async def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products by text query in local database"""
        try:
            result = await self.product_tool.search_products(query, limit=limit)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []

    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get specific product by ID from local database"""
        try:
            result = await self.product_tool.get_product_by_id(product_id)
            return result.get("product") if result.get("success") else None
        except Exception as e:
            logger.error(f"Error getting product by ID: {str(e)}")
            return None


class DefaultCatalogDecisionEngine(ICatalogDecisionEngine):
    """Default decision engine (can be replaced with more sophisticated logic)"""

    async def should_show_catalog(
        self, user_message: str, intent_analysis: Dict[str, Any], available_products: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """Simple decision logic"""

        if len(available_products) < 2:
            return False, "Insufficient products"

        # Check for catalog-friendly keywords
        catalog_keywords = ["ver", "mostrar", "catálogo", "productos", "opciones"]
        message_lower = user_message.lower()

        if any(keyword in message_lower for keyword in catalog_keywords):
            return True, "Contains catalog keywords"

        return len(available_products) >= 5, f"Product count decision: {len(available_products)}"

    async def select_catalog_products(
        self, products: List[Dict[str, Any]], user_intent: Dict[str, Any], max_products: int = 10
    ) -> List[Dict[str, Any]]:
        """Simple product selection"""

        # Filter products with required fields
        valid_products = [p for p in products if p.get("id") and p.get("name")]

        # Sort by price availability, then name
        valid_products.sort(key=lambda p: (0 if p.get("price") else 1, p.get("name", "").lower()))

        return valid_products[:max_products]
