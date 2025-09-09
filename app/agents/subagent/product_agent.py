"""
Agente especializado en consultas de productos
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast

from langchain_core.documents import Document

from app.config.settings import get_settings

from ..integrations.chroma_integration import ChromaDBIntegration
from ..integrations.ollama_integration import OllamaIntegration
from ..tools.product_tool import ProductTool
from ..utils.tracing import trace_async_method
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

        # Initialize ChromaDB integration for semantic search (all products)
        all_products_path = os.path.join(get_settings().OLLAMA_API_CHROMADB, "products", "all_products")
        self.chroma = ChromaDBIntegration(all_products_path)
        self.chroma_collection = "products_all_products"

        # Configure search thresholds (lower threshold for better recall)
        self.min_chroma_results = 2
        self.similarity_threshold = 0.5  # Lowered from 0.7 for better semantic matching

        # Always use PostgreSQL database as fallback
        self.data_source = "database"

    @trace_async_method(
        name="product_agent_process",
        run_type="chain",
        metadata={"agent_type": "product", "data_source": "database"},
        extract_state=True,
    )
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

            # Step 1: Try ChromaDB semantic search first
            self.logger.debug("Attempting ChromaDB semantic search...")
            chroma_data = await self._query_products_from_chroma(message, intent_analysis)

            products = []
            response_text = ""
            source = "chroma"

            # Check if ChromaDB returned sufficient relevant results
            chroma_products = chroma_data.get("products", [])
            chroma_success = chroma_data.get("success", False)

            if chroma_success and len(chroma_products) >= self.min_chroma_results:
                # ChromaDB found sufficient results - use them
                products = chroma_products
                self.logger.info(f"Using ChromaDB results: {len(products)} products found")

                # Generate response using ChromaDB-specific AI prompt
                response_text = await self._generate_chroma_ai_response(products, message, intent_analysis, chroma_data)

            else:
                # Step 2: Fallback to database search
                self.logger.info(
                    f"ChromaDB insufficient results ({len(chroma_products)}),\
                    falling back to database search..."
                )

                products_data = await self._get_products_from_db(intent_analysis)

                if not products_data["success"]:
                    raise Exception(f"Error fetching products: {products_data.get('error', 'Unknown error')}")

                products = products_data.get("products", [])
                source = "database"

                # Generate AI-powered response using traditional method
                if not products:
                    response_text = await self._generate_no_results_response(message, intent_analysis)
                else:
                    response_text = await self._generate_ai_response(products, message, intent_analysis)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "products": products,
                    "intent": intent_analysis,
                    "source": source,
                    "chroma_metadata": chroma_data if source == "chroma" else None,
                },
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
        prompt = f"""# USER MESSAGE
"{message}"

# INSTRUCTIONS
You are analyzing a user's product inquiry for an e-commerce system. Extract the user's intent and respond with JSON:

{{
  "intent": "show_general_catalog|search_specific_products|search_by_category|search_by_brand|search_by_price
    |get_product_details",
  "search_terms": ["specific", "product", "terms"],
  "category": "category_name_or_null",
  "brand": "brand_name_or_null", 
  "price_min": float_or_null,
  "price_max": float_or_null,
  "specific_product": "exact_product_name_or_null",
  "wants_stock_info": boolean,
  "wants_featured": boolean,
  "wants_sale": boolean,
  "action_needed": "show_featured|search_products|search_category|search_brand|search_price"
}}

INTENT ANALYSIS:
- show_general_catalog: User asks what products are available, general catalog inquiry ("what products do you have",
    "show me your products")
- search_specific_products: User wants specific products ("show me laptops", "I need a phone")
- search_by_category: User mentions a specific category
- search_by_brand: User mentions a specific brand  
- search_by_price: User mentions price range
- get_product_details: User asks about a specific product

For search_terms, only include meaningful product-related words, not filler words."""

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
        """Fetch products from database based on AI intent analysis."""
        intent = intent_analysis.get("intent", "show_general_catalog")
        action_needed = intent_analysis.get("action_needed", "show_featured")

        # Use AI-determined action to decide what to fetch
        if action_needed == "show_featured" or intent == "show_general_catalog":
            # For general catalog requests, show featured products
            return await self.product_tool("featured", limit=self.max_products_shown)

        elif action_needed == "search_category" or intent == "search_by_category":
            category = intent_analysis.get("category")
            if category:
                return await self.product_tool("by_category", category=category, limit=self.max_products_shown)

        elif action_needed == "search_brand" or intent == "search_by_brand":
            brand = intent_analysis.get("brand")
            if brand:
                return await self.product_tool("by_brand", brand=brand, limit=self.max_products_shown)

        elif action_needed == "search_price" or intent == "search_by_price":
            price_min = intent_analysis.get("price_min")
            price_max = intent_analysis.get("price_max")
            if price_min or price_max:
                return await self.product_tool(
                    "by_price_range",
                    min_price=price_min,
                    max_price=price_max,
                    limit=self.max_products_shown,
                )

        elif action_needed == "search_products" or intent in ["search_specific_products", "get_product_details"]:
            # Use AI-extracted search terms for product search
            search_terms = intent_analysis.get("search_terms", [])
            specific_product = intent_analysis.get("specific_product")

            if specific_product:
                return await self.product_tool("search", search_term=specific_product, limit=self.max_products_shown)
            elif search_terms:
                search_term = " ".join(search_terms)
                return await self.product_tool("search", search_term=search_term, limit=self.max_products_shown)

        # Check for special preferences
        if intent_analysis.get("wants_featured"):
            return await self.product_tool("featured", limit=self.max_products_shown)

        if intent_analysis.get("wants_sale"):
            return await self.product_tool("on_sale", limit=self.max_products_shown)

        # Fallback: use advanced search with all available parameters
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

        search_params["in_stock"] = True
        search_params["limit"] = self.max_products_shown

        # If no specific search parameters, show featured products
        if not any(search_params.get(key) for key in ["search_term", "category", "brand", "min_price", "max_price"]):
            return await self.product_tool("featured", limit=self.max_products_shown)

        return await self.product_tool("advanced_search", **search_params)

    async def _query_products_from_chroma(self, user_query: str, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query products from ChromaDB using semantic search.

        Args:
            user_query: Original user query
            intent_analysis: AI-analyzed user intent

        Returns:
            Dict with success, products, and metadata
        """
        try:
            # Construct semantic search query in English for better embedding matching
            search_terms = intent_analysis.get("search_terms", [])
            category = intent_analysis.get("category")
            brand = intent_analysis.get("brand")
            specific_product = intent_analysis.get("specific_product")

            # Build comprehensive search query
            query_parts = []

            if specific_product:
                query_parts.append(f"product: {specific_product}")
            elif search_terms:
                query_parts.append(" ".join(search_terms))

            if category:
                query_parts.append(f"category: {category}")

            if brand:
                query_parts.append(f"brand: {brand}")

            # Fallback to original user query if no specific terms
            semantic_query = " ".join(query_parts) if query_parts else user_query

            self.logger.debug(f"ChromaDB semantic search query: '{semantic_query}'")

            # Perform semantic search (returns List[Tuple[Document, float]] when include_scores=True)
            results = await self.chroma.search_similar(
                collection_name=self.chroma_collection,
                query=semantic_query,
                k=10,  # Get more results to filter
                include_scores=True,
            )

            # Cast to correct type since we know include_scores=True returns tuples
            results = cast(List[Tuple[Document, float]], results)

            if not results:
                self.logger.info("No results from ChromaDB semantic search")
                return {"success": True, "products": [], "source": "chroma", "query": semantic_query}

            # Process results and extract product information
            products = []
            for result in results:
                try:
                    # Unpack the tuple (Document, score)
                    if isinstance(result, tuple) and len(result) == 2:
                        doc, score = result
                    else:
                        # Fallback if structure is unexpected
                        self.logger.warning(f"Unexpected result structure: {type(result)}")
                        continue

                    # Filter by similarity threshold
                    if score < self.similarity_threshold:
                        continue

                    # Parse metadata to reconstruct product data
                    metadata = doc.metadata
                    product_data = {
                        "id": metadata.get("product_id"),
                        "name": metadata.get("name", ""),
                        "description": metadata.get("description", ""),
                        "price": float(metadata.get("price", 0)),
                        "stock": int(metadata.get("stock", 0)),
                        "sku": metadata.get("sku", ""),
                        "category": {
                            "name": metadata.get("category_name", ""),
                            "display_name": metadata.get("category_display_name", ""),
                        },
                        "brand": {"name": metadata.get("brand_name", "")} if metadata.get("brand_name") else None,
                        "specs": metadata.get("specs", ""),
                        "similarity_score": float(score),
                    }

                    products.append(product_data)

                except Exception as e:
                    self.logger.warning(f"Error processing ChromaDB result: {e}")
                    continue

            # Sort by similarity score (descending)
            products.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

            # Limit to max products shown
            products = products[: self.max_products_shown]

            self.logger.info(
                f"ChromaDB found {len(products)} relevant products (similarity >= {self.similarity_threshold})"
            )

            return {
                "success": True,
                "products": products,
                "source": "chroma",
                "query": semantic_query,
                "total_results": len(results),
                "filtered_results": len(products),
            }

        except Exception as e:
            self.logger.error(f"Error querying ChromaDB: {str(e)}")
            return {"success": False, "error": str(e), "products": [], "source": "chroma"}

    async def _generate_chroma_ai_response(
        self,
        products: List[Dict[str, Any]],
        message: str,
        _: Dict[str, Any],
        chroma_metadata: Dict[str, Any],
    ) -> str:
        """Generate AI-powered response specifically for ChromaDB semantic search results."""
        # Prepare product information for AI in structured format
        product_info = []
        for product in products:
            info = {
                "name": product["name"],
                "brand": product.get("brand", {}).get("name", "N/A") if product.get("brand") else "N/A",
                "price": f"${product['price']:.2f}",
                "stock": "Available" if product["stock"] > 0 else "Out of stock",
                "stock_count": product["stock"],
                "category": product.get("category", {}).get("display_name", "N/A"),
                "description": product.get("description", "")[:150] + "..."
                if len(product.get("description", "")) > 150
                else product.get("description", ""),
                "specs": product.get("specs", "")[:100] + "..."
                if len(product.get("specs", "")) > 100
                else product.get("specs", ""),
                "similarity_score": product.get("similarity_score", 0),
                "sku": product.get("sku", ""),
            }
            product_info.append(info)

        # Create structured product data for the prompt
        products_json = []
        for info in product_info:
            products_json.append(f"""{{
    "name": "{info["name"]}",
    "brand": "{info["brand"]}",
    "price": "{info["price"]}",
    "stock": "{info["stock"]} ({info["stock_count"]} units)",
    "category": "{info["category"]}",
    "description": "{info["description"]}",
    "relevance": {info["similarity_score"]:.3f}
}}""")

        products_text = ",\n".join(products_json)

        # Enhanced English prompt for better multilingual understanding and processing
        prompt = f"""# E-COMMERCE PRODUCT SEARCH ASSISTANT

## USER QUERY
"{message}"

## LANGUAGE DETECTION & RESPONSE REQUIREMENT
IMPORTANT: Detect the language of the user's query and respond in the SAME language.
- If Spanish → Respond in Spanish
- If English → Respond in English  
- If Portuguese → Respond in Portuguese
- Default: Spanish

## SEMANTIC SEARCH RESULTS
Found {len(products)} relevant products from vector database:
[
{products_text}
]

## SEARCH METADATA
- Source: ChromaDB semantic search
- Query processed: "{chroma_metadata.get("query", message)}"
- Total results found: {chroma_metadata.get("total_results", 0)}
- Results after filtering: {chroma_metadata.get("filtered_results", len(products))}

## INSTRUCTIONS
You are a helpful multilingual e-commerce assistant. Based on the semantic search results above:

1. **ANALYZE LANGUAGE**: Detect user's language and respond accordingly
2. **ANALYZE RELEVANCE**: Review the similarity scores and product details
3. **PRIORITIZE RESULTS**: Focus on products with higher relevance scores (>0.7 excellent, >0.5 good)
4. **GENERATE RESPONSE**: Create a natural, conversational response that:
   - Highlights the most relevant products (top 3-5)
   - Includes key details: name, brand, price, stock status
   - Uses natural language and friendly tone
   - Includes relevant emojis moderately (1-3 max)
   - Mentions category if helpful for context
   - Suggests alternatives if needed

## RESPONSE FORMAT
- Maximum 6 lines
- Start with products found confirmation
- List top products with essential details
- End with helpful offer for more information

## QUALITY REQUIREMENTS
- **Language Match**: Respond in user's detected language
- **Accuracy**: All prices and product details must be exact
- **Relevance**: Prioritize higher similarity scores
- **Completeness**: Include stock status and key specifications
- **Tone**: Professional but friendly and helpful
- **Brevity**: Concise but informative

Generate your response now:"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7, model="llama3.2:1b")
            response = await llm.ainvoke(prompt)
            return response.content.strip()  # type: ignore
        except Exception as e:
            self.logger.error(f"Error generating ChromaDB AI response: {str(e)}")
            # Fallback to formatted response
            return self._format_chroma_fallback_response(products, chroma_metadata)

    def _format_chroma_fallback_response(self, products: List[Dict[str, Any]], _: Dict[str, Any]) -> str:
        """Fallback response formatting for ChromaDB results when AI fails."""
        if not products:
            return "🔍 Busqué en nuestro catálogo pero no encontré productos que coincidan exactamente con tu consulta.\
                ¿Podrías ser más específico?"

        count = len(products)
        response = f"🎯 Encontré {count} producto{'s' if count > 1 else ''} relevante{'s' if count > 1 else ''}\
            para tu búsqueda:\n\n"

        for i, product in enumerate(products[:5], 1):
            name = product["name"]
            brand = product.get("brand", {}).get("name", "") if product.get("brand") else ""
            price = product["price"]
            stock = product["stock"]

            response += f"{i}. **{name}**"
            if brand:
                response += f" ({brand})"
            response += f" - ${price:,.2f}"

            if stock > 0:
                response += f" ✅ ({stock} disponibles)"
            else:
                response += " ❌ Sin stock"
            response += "\n"

        response += "\n¿Te interesa alguno? Puedo darte más detalles. 🛒"
        return response

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

        prompt = f"""# USER QUERY
"{message}"

# LANGUAGE DETECTION
IMPORTANT: Detect the language of the user's query and respond in the SAME language.
- Spanish query → Respond in Spanish
- English query → Respond in English
- Portuguese query → Respond in Portuguese
- Default → Spanish

# SEARCH RESULTS
Found {len(products)} relevant products. Here's a summary of the main ones:
{chr(10).join(product_info[:5])}

# INSTRUCTIONS
Generate a brief response highlighting products, prices and stock availability:
- Be clear and friendly
- Maximum 5 lines
- Use emojis moderately (1-3 max)
- Match the user's language
- Include key product details (name, price, stock status)

Generate your response now:"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7, model="llama3.2:1b")
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating AI product response: {str(e)}")
            # Fallback to formatted response
            return self._generate_fallback_response(products, intent_analysis)

    async def _generate_no_results_response(self, message: str, intent_analysis: Dict[str, Any]) -> str:
        """Generate response when no products are found."""
        prompt = f"""# USER QUERY
User searched for: "{message}"

# INSTRUCTIONS
No matches found. Suggest 2 relevant alternatives.
- Maximum 3 lines.
- Be cordial and helpful.
- Respond in Spanish.
"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7, model="llama3.2:1b")
            response = await llm.ainvoke(prompt)
            return response.content  # type: ignore
        except Exception as e:
            logger.error(f"Error generating no results response: {str(e)}")
            return await self._generate_fallback_no_results(message, intent_analysis)

    def _generate_fallback_response(self, products: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> str:
        """Generate fallback response without AI."""
        print("Generating fallback response", intent_analysis)
        if len(products) == 1:
            return self._format_single_product(products[0])
        else:
            return self._format_multiple_products(products)

    async def _generate_fallback_no_results(self, message: str, intent_analysis: Dict[str, Any]) -> str:
        """Generate AI-powered fallback no results response."""
        intent_str = json.dumps(intent_analysis, indent=2)
        prompt = f"""# USER SEARCH
User searched for: "{message}"

# INTENT ANALYSIS
{intent_str}

# INSTRUCTIONS
No matching products found. Generate a helpful response that:
- Is empathetic and understanding
- Offers 2-3 specific alternatives based on the query
- Uses a conversational and friendly tone
- Maximum 4 lines
- Responds in Spanish
- Include relevant emojis"""

        try:
            # Use fast model for user-facing responses
            llm = self.ollama.get_llm(temperature=0.7, model="llama3.2:1b")
            response = await llm.ainvoke(prompt)
            return response.content.strip()  # type: ignore
        except Exception as e:
            logger.error(f"Error generating no results response: {str(e)}")
            return f"Lo siento, no encontré productos para '{message}'. ¿Te puedo ayudar con otra búsqueda? 🤔"

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
