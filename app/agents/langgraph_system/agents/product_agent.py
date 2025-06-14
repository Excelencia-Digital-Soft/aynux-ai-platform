"""
Agente especializado en consultas de productos
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..integrations.ollama_integration import OllamaIntegration
from ..tools.product_tool import ProductTool
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ProductAgent(BaseAgent):
    """Agente especializado en consultas específicas de productos y stock"""

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("product_agent", config or {}, ollama=ollama, postgres=postgres)

        # Configuración específica del agente
        self.max_products_shown = self.config.get("max_products_shown", 10)
        self.show_stock = self.config.get("show_stock", True)
        self.show_prices = self.config.get("show_prices", True)
        self.enable_recommendations = self.config.get("enable_recommendations", True)

        # Initialize tools
        self.product_tool = ProductTool()
        self.ollama = ollama or OllamaIntegration()

    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa consultas de productos usando AI y base de datos.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Analyze user intent using AI
            intent_analysis = await self._analyze_user_intent(message)

            # Search products based on intent
            products_data = await self._get_products_from_db(intent_analysis)

            if not products_data["success"]:
                raise Exception(f"Error fetching products: {products_data.get('error', 'Unknown error')}")

            products = products_data.get("products", [])

            # Generate AI-powered response
            if not products:
                response_text = await self._generate_no_results_response(message, intent_analysis)
            else:
                response_text = await self._generate_ai_response(products, message, intent_analysis)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {"products": products, "intent": intent_analysis},
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in product agent: {str(e)}")

            error_response = "Disculpa, tuve un problema consultando los productos. ¿Podrías reformular tu pregunta?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_user_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user intent using AI."""
        prompt = f"""# MENSAJE DEL USUARIO
"{message}"

# INSTRUCCIONES
Extrae del mensaje la intención del usuario y responde en JSON con los siguientes campos:
{{
  "intent": "search_general|search_by_brand|search_by_category|get_specific|search_by_price",
  "search_terms": ["..."],
  "category": "nombre|null",
  "brand": "marca|null",
  "price_min": float|null,
  "price_max": float|null,
  "specific_product": "nombre|null",
  "wants_stock_info": bool,
  "wants_featured": bool,
  "wants_sale": bool
}}"""

        try:
            llm = self.ollama.get_llm(temperature=0.3)
            response = await llm.ainvoke(prompt)
            # Try to parse as JSON, fallback to basic intent if fails
            try:
                return json.loads(response.content)
            except Exception:
                return {
                    "intent": "search_general",
                    "search_terms": message.split(),
                    "category": None,
                    "brand": None,
                    "price_min": None,
                    "price_max": None,
                    "specific_product": None,
                    "wants_stock_info": False,
                    "wants_featured": False,
                    "wants_sale": False,
                }
        except Exception as e:
            logger.error(f"Error analyzing product intent: {str(e)}")
            return {
                "intent": "search_general",
                "search_terms": message.split(),
                "category": None,
                "brand": None,
                "price_min": None,
                "price_max": None,
                "specific_product": None,
                "wants_stock_info": False,
                "wants_featured": False,
                "wants_sale": False,
            }

    async def _get_products_from_db(self, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch products from database based on intent analysis."""
        intent = intent_analysis.get("intent", "search_general")

        # Check for special intents first
        if intent_analysis.get("wants_featured") or intent == "featured_products":
            return await self.product_tool("featured", limit=self.max_products_shown)

        if intent_analysis.get("wants_sale") or intent == "sale_products":
            return await self.product_tool("on_sale", limit=self.max_products_shown)

        # Handle specific product search
        if intent == "get_specific" and intent_analysis.get("specific_product"):
            search_term = intent_analysis["specific_product"]
            return await self.product_tool("search", search_term=search_term, limit=1)

        # Handle category-based search
        if intent == "search_by_category" and intent_analysis.get("category"):
            return await self.product_tool(
                "by_category", category=intent_analysis["category"], limit=self.max_products_shown
            )

        # Handle brand-based search
        if intent == "search_by_brand" and intent_analysis.get("brand"):
            return await self.product_tool("by_brand", brand=intent_analysis["brand"], limit=self.max_products_shown)

        # Handle price range search
        price_filter = intent_analysis.get("price_min") or intent_analysis.get("price_max")
        if intent == "search_by_price" and price_filter:
            return await self.product_tool(
                "by_price_range",
                min_price=intent_analysis.get("price_min"),
                max_price=intent_analysis.get("price_max"),
                limit=self.max_products_shown,
            )

        # Advanced search for complex queries
        search_params = {}

        if intent_analysis.get("search_terms"):
            search_params["search_term"] = " ".join(intent_analysis["search_terms"])

        if intent_analysis.get("category"):
            search_params["category"] = intent_analysis["category"]

        if intent_analysis.get("brand"):
            search_params["brand"] = intent_analysis["brand"]

        if intent_analysis.get("price_min"):
            search_params["min_price"] = intent_analysis["price_min"]

        if intent_analysis.get("price_max"):
            search_params["max_price"] = intent_analysis["price_max"]

        search_params["in_stock"] = True  # Default to showing only in-stock items
        search_params["limit"] = self.max_products_shown

        return await self.product_tool("advanced_search", **search_params)

    async def _generate_ai_response(
        self, products: List[Dict[str, Any]], message: str, intent_analysis: Dict[str, Any]
    ) -> str:
        """Generate AI-powered response based on products and user intent."""
        # Prepare product information for AI
        product_info = []
        for product in products[: self.max_products_shown]:
            info = f"- {product['name']}"
            if product.get("brand", {}).get("name"):
                info += f" ({product['brand']['name']})"

            if self.show_prices:
                info += f" - ${product['price']:.2f}"

            if self.show_stock:
                stock = product["stock"]
                if stock > 0:
                    info += f" ✅ ({stock} en stock)"
                else:
                    info += " ❌ (Sin stock)"

            if product.get("category", {}).get("display_name"):
                info += f" | Categoría: {product['category']['display_name']}"

            if product.get("description"):
                desc_text = product["description"]
                desc = desc_text[:100] + "..." if len(desc_text) > 100 else desc_text
                info += f" | {desc}"

            product_info.append(info)

        prompt = f"""# CONSULTA DEL USUARIO
"{message}"

# RESULTADOS
Se encontraron {len(products)} productos relevantes. Aquí un resumen de los principales:
{chr(10).join(product_info[:5])}

# INSTRUCCIONES
Responde brevemente destacando productos, precios y stock.
- Sé claro y amigable.
- No excedas 4 líneas.
- Puedes usar emojis moderadamente.
"""

        try:
            llm = self.ollama.get_llm(temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating AI product response: {str(e)}")
            # Fallback to formatted response
            return self._generate_fallback_response(products, intent_analysis)

    async def _generate_no_results_response(self, message: str, intent_analysis: Dict[str, Any]) -> str:
        """Generate response when no products are found."""
        prompt = f"""# CONSULTA
El usuario buscó: "{message}"

# INSTRUCCIONES
No se encontraron coincidencias. 
Sugiere 2 alternativas relevantes.
- Máximo 3 líneas.
- Sé cordial.
"""

        try:
            llm = self.ollama.get_llm(temperature=0.7)
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating no results response: {str(e)}")
            return await self._generate_fallback_no_results(message, intent_analysis)

    def _generate_fallback_response(self, products: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> str:
        """Generate fallback response without AI."""
        if len(products) == 1:
            return self._format_single_product(products[0])
        else:
            return self._format_multiple_products(products)

    async def _generate_fallback_no_results(self, message: str, intent_analysis: Dict[str, Any]) -> str:
        """Generate AI-powered fallback no results response with multiple attempts."""
        prompts = [
            # First attempt - detailed and contextual
            f"""# CONSULTA SIN RESULTADOS
El usuario buscó: "{message}"

# ANÁLISIS DE INTENCIÓN
{json.dumps(intent_analysis, indent=2)}

# INSTRUCCIONES
No se encontraron productos que coincidan. Genera una respuesta que:
- Sea empática y comprensiva
- Ofrezca 2-3 alternativas específicas basadas en la consulta
- Use un tono conversacional y amigable
- Máximo 4 líneas
- Incluya emojis relevantes""",
            # Second attempt - simpler approach
            f"""El usuario buscó "{message}" pero no hay resultados.

Responde de forma amigable ofreciendo:
1. Buscar en categorías similares
2. Mostrar productos relacionados
3. Ayuda con otra búsqueda

Sé breve y cordial.""",
            # Third attempt - very simple
            f'Usuario buscó "{message}" sin resultados. Ofrece ayuda alternativa en 2-3 líneas.',
        ]

        for attempt, prompt in enumerate(prompts, 1):
            try:
                # Use different temperature for each attempt
                temperature = 0.7 if attempt == 1 else 0.5 if attempt == 2 else 0.3
                llm = self.ollama.get_llm(temperature=temperature)
                response = await llm.ainvoke(prompt)

                if response.content and len(response.content.strip()) > 20:  # type: ignore
                    logger.info(f"AI fallback response generated on attempt {attempt}")
                    return response.content.strip()  # type: ignore

            except Exception as e:
                logger.warning(f"AI fallback attempt {attempt} failed: {str(e)}")
                continue

        # Final hardcoded fallback if all AI attempts fail
        logger.error("All AI fallback attempts failed, using hardcoded response")

        # Dynamic hardcoded response based on intent analysis
        search_term = message
        suggestions = []

        if intent_analysis.get("category"):
            suggestions.append(f"• Buscar en la categoría {intent_analysis['category']}")
        else:
            suggestions.append("• Buscar en una categoría específica")

        if intent_analysis.get("brand"):
            suggestions.append(f"• Ver otros productos de {intent_analysis['brand']}")
        else:
            suggestions.append("• Te muestre productos similares")

        suggestions.append("• Te ayude con otra consulta")

        return f"""No encontré productos que coincidan con "{search_term}". 

¿Te gustaría que:
{chr(10).join(suggestions)}

¿Qué prefieres? 🤔""".strip()

    def _format_single_product(self, product: Dict[str, Any]) -> str:
        """Format response for a single product."""
        name = product.get("name", "Producto")
        price = product.get("price", 0)
        stock = product.get("stock", 0) if self.show_stock else None
        description = product.get("description", "")
        brand = product.get("brand", {}).get("name", "")
        category = product.get("category", {}).get("display_name", "")

        response = f"📱 **{name}**"
        if brand:
            response += f" ({brand})"
        response += "\n"

        if self.show_prices and price:
            response += f"💰 Precio: ${price:,.2f}\n"

        if stock is not None:
            if stock > 0:
                response += f"✅ En stock ({stock} disponibles)\n"
            else:
                response += "❌ Sin stock\n"

        if category:
            response += f"📂 Categoría: {category}\n"

        if description:
            response += f"\n{description}\n"

        response += "\n¿Te interesa este producto? ¿Necesitas más información?"

        return response

    def _format_multiple_products(self, products: List[Dict[str, Any]]) -> str:
        """Format response for multiple products."""
        response = f"Encontré {len(products)} productos que podrían interesarte:\n\n"

        for i, product in enumerate(products, 1):
            name = product.get("name", f"Producto {i}")
            price = product.get("price", 0)
            stock = product.get("stock", 0) if self.show_stock else None
            brand = product.get("brand", {}).get("name", "")

            response += f"{i}. **{name}**"
            if brand:
                response += f" ({brand})"

            if self.show_prices and price:
                response += f" - ${price:,.2f}"

            if stock is not None:
                if stock > 0:
                    response += " ✅"
                else:
                    response += " ❌"

            response += "\n"

        response += "\n¿Te interesa alguno en particular? Puedo darte más detalles."

        return response
