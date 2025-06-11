"""
Agente especializado en consultas de productos
"""

import json
from typing import Any, Dict, List, Optional

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState


class ProductAgent(BaseAgent):
    """Agente especializado en consultas específicas de productos y stock"""

    def __init__(self, vector_store, db_connection, llm):
        super().__init__("product_agent")
        self.vector_store = vector_store
        self.db = db_connection
        self.llm = llm

        # Inicializar herramientas
        self.tools = [
            ProductSearchTool(vector_store, db_connection),
            StockVerificationTool(db_connection),
            PriceCalculatorTool(),
            ProductComparisonTool(llm),
        ]

    async def _process_internal(self, state: SharedState) -> Dict[str, Any]:
        """Procesa consultas sobre productos específicos"""
        user_message = state.get_last_user_message()
        entities = {}
        entities = state.current_intent.entities if state.current_intent else {}

        # Determinar tipo de consulta de producto
        query_type = await self._determine_query_type(user_message, entities)

        if query_type == "search":
            return await self._handle_product_search(state, user_message, entities)
        elif query_type == "stock_check":
            return await self._handle_stock_check(state, entities)
        elif query_type == "price_inquiry":
            return await self._handle_price_inquiry(state, user_message, entities)
        elif query_type == "comparison":
            return await self._handle_product_comparison(state, user_message)
        else:
            return await self._handle_general_product_query(state, user_message)

    async def _determine_query_type(self, message: str, entities: Dict) -> str:
        """Determina el tipo de consulta sobre productos"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["comparar", "vs", "versus", "diferencia"]):
            return "comparison"
        elif any(word in message_lower for word in ["stock", "disponible", "hay", "quedan"]):
            return "stock_check"
        elif any(word in message_lower for word in ["precio", "costo", "vale", "cuesta"]):
            return "price_inquiry"
        elif entities.get("product_categories") or entities.get("brands"):
            return "search"
        else:
            return "general"

    async def _handle_product_search(self, state: SharedState, message: str, entities: Dict) -> Dict[str, Any]:
        """Maneja búsquedas de productos"""
        # Construir query de búsqueda mejorada
        search_query = await self._build_search_query(message, entities)

        # Buscar productos
        products = await self.tools[0].search_products(
            query=search_query, filters=self._build_filters(entities), limit=5
        )

        if not products:
            return await self._handle_no_products_found(message, entities)

        # Verificar stock para cada producto
        for product in products:
            stock_info = await self.tools[1].check_stock(product["id"])
            product["stock_info"] = stock_info

        # Calcular precios según tier del cliente
        customer_tier = state.customer.tier if state.customer else "basic"
        for product in products:
            pricing = await self.tools[2].calculate_price(product, customer_tier)
            product["pricing"] = pricing

        # Generar respuesta
        response_text = self._format_product_search_response(products, len(products), customer_tier)

        return {
            "text": response_text,
            "data": {"products": products, "search_query": search_query, "filters_applied": entities},
            "tools_used": ["ProductSearchTool", "StockVerificationTool", "PriceCalculatorTool"],
        }

    async def _handle_stock_check(self, state: SharedState, entities: Dict) -> Dict[str, Any]:
        """Verifica stock de productos específicos"""
        # Buscar productos mencionados
        product_refs = entities.get("product_references", [])

        if not product_refs:
            # Buscar por otras entidades
            products = await self._find_products_by_entities(entities)
        else:
            products = await self._find_products_by_refs(product_refs)

        if not products:
            return {
                "text": "No pude identificar el producto específico. ¿Podrías darme más detalles como el nombre o modelo?",
                "data": {},
                "tools_used": [],
            }

        # Verificar stock detallado
        stock_details = []
        for product in products:
            stock_info = await self.tools[1].check_detailed_stock(product["id"])
            stock_details.append({"product": product, "stock": stock_info})

        # Generar respuesta de stock
        response_text = self._format_stock_response(stock_details)

        return {
            "text": response_text,
            "data": {"stock_details": stock_details},
            "tools_used": ["StockVerificationTool"],
        }

    async def _handle_price_inquiry(self, state: SharedState, message: str, entities: Dict) -> Dict[str, Any]:
        """Maneja consultas de precios"""
        # Buscar productos relevantes
        products = await self.tools[0].search_products(query=message, filters=self._build_filters(entities), limit=3)

        if not products:
            return await self._handle_no_products_found(message, entities)

        # Calcular precios con descuentos
        customer_tier = state.customer.tier if state.customer else "basic"
        price_details = []

        for product in products:
            # Precio base
            base_price = product["price"]

            # Calcular con descuentos y promociones
            pricing = await self.tools[2].calculate_detailed_price(product, customer_tier, include_promotions=True)

            price_details.append({"product": product, "pricing": pricing})

        # Generar respuesta de precios
        response_text = self._format_price_response(price_details, customer_tier)

        return {
            "text": response_text,
            "data": {"price_details": price_details},
            "tools_used": ["ProductSearchTool", "PriceCalculatorTool"],
        }

    async def _handle_product_comparison(self, state: SharedState, message: str) -> Dict[str, Any]:
        """Maneja comparaciones entre productos"""
        # Extraer productos a comparar
        products_to_compare = await self._extract_products_for_comparison(message)

        if len(products_to_compare) < 2:
            return {
                "text": "Para comparar productos, necesito que menciones al menos 2 productos específicos. Por ejemplo: 'Compara Dell XPS 13 vs MacBook Air'",
                "data": {},
                "tools_used": [],
            }

        # Obtener detalles de cada producto
        product_details = []
        for product_ref in products_to_compare:
            products = await self.tools[0].search_products(query=product_ref, limit=1)
            if products:
                product_details.append(products[0])

        if len(product_details) < 2:
            return {
                "text": "No pude encontrar todos los productos mencionados. Por favor, verifica los nombres.",
                "data": {},
                "tools_used": ["ProductSearchTool"],
            }

        # Realizar comparación
        comparison = await self.tools[3].compare_products(product_details)

        # Generar respuesta de comparación
        response_text = self._format_comparison_response(comparison)

        return {
            "text": response_text,
            "data": {"comparison": comparison, "products_compared": product_details},
            "tools_used": ["ProductSearchTool", "ProductComparisonTool"],
        }

    async def _handle_general_product_query(self, state: SharedState, message: str) -> Dict[str, Any]:
        """Maneja consultas generales sobre productos"""
        # Búsqueda general semántica
        products = await self.tools[0].semantic_search(message, limit=4)

        if not products:
            return await self._suggest_alternatives(message)

        # Enriquecer con información básica
        for product in products:
            # Stock básico
            stock = await self.tools[1].check_stock(product["id"])
            product["available"] = stock["in_stock"]

            # Precio para el cliente
            if state.customer:
                pricing = await self.tools[2].calculate_price(product, state.customer.tier)
                product["customer_price"] = pricing["final_price"]

        # Generar respuesta
        response_text = "🔍 Encontré estos productos que podrían interesarte:\n\n"

        for idx, product in enumerate(products, 1):
            response_text += f"**{idx}. {product['name']}**\n"
            response_text += f"   {self._truncate_text(product.get('description', ''), 80)}\n"
            response_text += f"   💰 Precio: ${product.get('customer_price', product['price']):,.2f}\n"
            response_text += f"   📦 {'Disponible' if product['available'] else 'Sin stock'}\n\n"

        response_text += "¿Te gustaría más información sobre alguno de estos productos?"

        return {
            "text": response_text,
            "data": {"products": products},
            "tools_used": ["ProductSearchTool", "StockVerificationTool", "PriceCalculatorTool"],
        }

    # Métodos auxiliares
    async def _build_search_query(self, message: str, entities: Dict) -> str:
        """Construye una query de búsqueda optimizada"""
        query_parts = [message]

        # Añadir marcas si se mencionaron
        if entities.get("brands"):
            query_parts.extend(entities["brands"])

        # Añadir especificaciones técnicas
        if entities.get("technical_specs"):
            specs = entities["technical_specs"]
            for key, value in specs.items():
                query_parts.append(f"{key} {value}")

        return " ".join(query_parts)

    def _build_filters(self, entities: Dict) -> Dict[str, Any]:
        """Construye filtros para la búsqueda"""
        filters = {}

        if entities.get("product_categories"):
            filters["category"] = entities["product_categories"]

        if entities.get("brands"):
            filters["brand"] = entities["brands"]

        if entities.get("budget"):
            filters["max_price"] = entities["budget"]

        return filters

    def _format_product_search_response(self, products: List[Dict], total_found: int, customer_tier: str) -> str:
        """Formatea respuesta de búsqueda de productos"""
        if customer_tier in ["premium", "vip"]:
            response = f"🌟 Como cliente {customer_tier}, tienes acceso a precios especiales:\n\n"
        else:
            response = f"📦 Encontré {total_found} productos que coinciden con tu búsqueda:\n\n"

        for idx, product in enumerate(products, 1):
            # Emoji según disponibilidad
            stock_emoji = "✅" if product["stock_info"]["in_stock"] else "❌"

            response += f"**{idx}. {product['name']}** {stock_emoji}\n"

            # Descripción breve
            if product.get("description"):
                response += f"   {self._truncate_text(product['description'], 100)}\n"

            # Precio con descuento si aplica
            pricing = product["pricing"]
            if pricing.get("discount_percentage", 0) > 0:
                response += f"   💰 ~~${pricing['original_price']:,.2f}~~ "
                response += f"**${pricing['final_price']:,.2f}** "
                response += f"(-{pricing['discount_percentage']}%)\n"
            else:
                response += f"   💰 ${pricing['final_price']:,.2f}\n"

            # Stock
            stock = product["stock_info"]
            if stock["in_stock"]:
                if stock["quantity"] < 5:
                    response += f"   ⚠️ ¡Últimas {stock['quantity']} unidades!\n"
                else:
                    response += f"   📦 Disponible inmediatamente\n"
            else:
                response += f"   ❌ Sin stock (reposición: {stock.get('restock_date', 'por confirmar')})\n"

            # Características principales
            if product.get("key_features"):
                response += "   🔹 " + " • ".join(product["key_features"][:3]) + "\n"

            response += "\n"

        # Call to action
        response += "💬 Responde con el número del producto para más detalles, "
        response += "o dime si quieres ver más opciones."

        return response

    def _format_stock_response(self, stock_details: List[Dict]) -> str:
        """Formatea respuesta de verificación de stock"""
        response = "📊 **Estado de Stock:**\n\n"

        for detail in stock_details:
            product = detail["product"]
            stock = detail["stock"]

            response += f"**{product['name']}**\n"

            if stock["in_stock"]:
                response += f"✅ Disponible: {stock['quantity']} unidades\n"

                # Detalles por ubicación si hay
                if stock.get("by_location"):
                    response += "📍 Disponibilidad por tienda:\n"
                    for location, qty in stock["by_location"].items():
                        response += f"   • {location}: {qty} unidades\n"

                # Información de reserva
                if stock["quantity"] < 10:
                    response += "⚠️ Stock limitado - Te recomiendo reservar pronto\n"

            else:
                response += "❌ Sin stock actualmente\n"

                if stock.get("restock_date"):
                    response += f"📅 Reposición esperada: {stock['restock_date']}\n"

                if stock.get("alternatives"):
                    response += "💡 Productos similares disponibles:\n"
                    for alt in stock["alternatives"][:2]:
                        response += f"   • {alt['name']}\n"

            response += "\n"

        response += "¿Te gustaría reservar algún producto o ver alternativas?"

        return response

    def _format_price_response(self, price_details: List[Dict], customer_tier: str) -> str:
        """Formatea respuesta de consulta de precios"""
        response = "💰 **Información de Precios:**\n\n"

        for detail in price_details:
            product = detail["product"]
            pricing = detail["pricing"]

            response += f"**{product['name']}**\n"
            response += f"Precio regular: ${pricing['base_price']:,.2f}\n"

            # Descuentos aplicados
            if pricing.get("discounts"):
                response += "Descuentos aplicados:\n"
                for discount in pricing["discounts"]:
                    response += f"   • {discount['name']}: -{discount['amount']}\n"

            # Precio final
            response += f"**Tu precio: ${pricing['final_price']:,.2f}**\n"

            # Ahorro
            if pricing["total_savings"] > 0:
                response += f"💸 Ahorras: ${pricing['total_savings']:,.2f} "
                response += f"({pricing['savings_percentage']:.0f}%)\n"

            # Opciones de pago
            if pricing.get("payment_options"):
                response += "💳 Opciones de pago:\n"
                for option in pricing["payment_options"]:
                    response += f"   • {option['name']}: {option['description']}\n"

            response += "\n"

        # Beneficios por tier
        if customer_tier in ["premium", "vip"]:
            response += f"✨ Como cliente {customer_tier}, "
            response += "estos precios ya incluyen tu descuento exclusivo.\n"

        return response

    def _format_comparison_response(self, comparison: Dict) -> str:
        """Formatea respuesta de comparación de productos"""
        response = "📊 **Comparación de Productos:**\n\n"

        # Resumen
        response += f"Comparando: {comparison['product1']['name']} vs {comparison['product2']['name']}\n\n"

        # Tabla de comparación
        response += "**Especificaciones:**\n"
        for spec, values in comparison["specs_comparison"].items():
            response += f"• {spec}:\n"
            response += f"  - {comparison['product1']['name']}: {values['product1']}\n"
            response += f"  - {comparison['product2']['name']}: {values['product2']}\n"

        response += "\n**Precios:**\n"
        response += f"• {comparison['product1']['name']}: ${comparison['product1']['price']:,.2f}\n"
        response += f"• {comparison['product2']['name']}: ${comparison['product2']['price']:,.2f}\n"

        # Ventajas de cada uno
        response += "\n**Ventajas principales:**\n"
        response += f"\n{comparison['product1']['name']}:\n"
        for advantage in comparison["advantages"]["product1"]:
            response += f"✓ {advantage}\n"

        response += f"\n{comparison['product2']['name']}:\n"
        for advantage in comparison["advantages"]["product2"]:
            response += f"✓ {advantage}\n"

        # Recomendación
        if comparison.get("recommendation"):
            response += f"\n💡 **Recomendación:** {comparison['recommendation']}\n"

        return response

    async def _handle_no_products_found(self, query: str, entities: Dict) -> Dict[str, Any]:
        """Maneja cuando no se encuentran productos"""
        response = f"🔍 No encontré productos exactos para '{query}'\n\n"

        # Sugerir alternativas
        suggestions = await self._get_search_suggestions(query, entities)

        if suggestions:
            response += "Pero te puedo sugerir:\n\n"
            for suggestion in suggestions:
                response += f"• {suggestion}\n"
        else:
            response += "Te sugiero:\n"
            response += "• Usar términos más generales\n"
            response += "• Verificar la ortografía\n"
            response += "• Buscar por categoría\n"

        response += "\n¿Qué te gustaría buscar?"

        return {"text": response, "data": {"original_query": query, "suggestions": suggestions}, "tools_used": []}

    async def _get_search_suggestions(self, query: str, entities: Dict) -> List[str]:
        """Obtiene sugerencias de búsqueda"""
        # En producción esto usaría un servicio de sugerencias
        return ["Laptops gaming con RTX", "Computadoras para oficina", "Accesorios para PC"]

    async def _extract_products_for_comparison(self, message: str) -> List[str]:
        """Extrae productos mencionados para comparación"""
        # Buscar patrones de comparación
        patterns = [
            r"compara[r]?\s+(.+?)\s+(?:con|vs|versus|y)\s+(.+)",
            r"diferencia entre\s+(.+?)\s+y\s+(.+)",
            r"(.+?)\s+o\s+(.+?)(?:\?|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return [match.group(1).strip(), match.group(2).strip()]

        return []

    async def _find_products_by_entities(self, entities: Dict) -> List[Dict]:
        """Encuentra productos basándose en entidades extraídas"""
        # Implementación simplificada
        return []

    async def _find_products_by_refs(self, refs: List[str]) -> List[Dict]:
        """Encuentra productos por referencias específicas"""
        # Implementación simplificada
        return []

    async def _suggest_alternatives(self, query: str) -> Dict[str, Any]:
        """Sugiere alternativas cuando no hay resultados"""
        return {
            "text": "No encontré productos específicos, pero puedo mostrarte nuestras categorías principales. ¿Te gustaría explorar alguna?",
            "data": {},
            "tools_used": [],
        }


# Herramientas del ProductAgent
class ProductSearchTool:
    """Herramienta de búsqueda de productos"""

    def __init__(self, vector_store, db_connection):
        self.vector_store = vector_store
        self.db = db_connection

    async def search_products(self, query: str, filters: Dict[str, Any] = None, limit: int = 10) -> List[Dict]:
        """Busca productos con filtros opcionales"""
        # Construir filtro para vector store
        vector_filter = {"type": "product"}
        if filters:
            vector_filter.update(filters)

        try:
            # Búsqueda semántica
            results = await self.vector_store.asimilarity_search_with_score(query, k=limit, filter=vector_filter)

            # Convertir resultados
            products = []
            for doc, score in results:
                product_data = json.loads(doc.page_content) if isinstance(doc.page_content, str) else doc.page_content
                product_data["relevance_score"] = score
                products.append(product_data)

            return products

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    async def semantic_search(self, query: str, limit: int = 10) -> List[Dict]:
        """Búsqueda semántica sin filtros"""
        return await self.search_products(query, limit=limit)


class StockVerificationTool:
    """Herramienta de verificación de stock"""

    def __init__(self, db_connection):
        self.db = db_connection

    async def check_stock(self, product_id: str) -> Dict[str, Any]:
        """Verifica stock básico de un producto"""
        # En producción esto consultaría la BD
        # Simulación
        import random

        in_stock = random.choice([True, True, True, False])  # 75% de probabilidad de tener stock
        quantity = random.randint(0, 50) if in_stock else 0

        return {"product_id": product_id, "in_stock": in_stock, "quantity": quantity}

    async def check_detailed_stock(self, product_id: str) -> Dict[str, Any]:
        """Verifica stock detallado incluyendo ubicaciones"""
        basic_stock = await self.check_stock(product_id)

        # Añadir detalles adicionales
        if basic_stock["in_stock"]:
            basic_stock["by_location"] = {
                "Tienda Principal": basic_stock["quantity"] // 2,
                "Bodega Central": basic_stock["quantity"] // 2,
                "Disponible Online": basic_stock["quantity"],
            }
        else:
            basic_stock["restock_date"] = "15 de diciembre"
            basic_stock["alternatives"] = [
                {"id": "alt1", "name": "Producto Similar A"},
                {"id": "alt2", "name": "Producto Similar B"},
            ]

        return basic_stock


class PriceCalculatorTool:
    """Herramienta de cálculo de precios"""

    def calculate_discount_percentage(self, tier: str) -> float:
        """Calcula porcentaje de descuento por tier"""
        discounts = {"basic": 0, "premium": 5, "vip": 10}
        return discounts.get(tier, 0)

    async def calculate_price(self, product: Dict, customer_tier: str) -> Dict[str, Any]:
        """Calcula precio final para un cliente"""
        base_price = product.get("price", 0)
        discount_pct = self.calculate_discount_percentage(customer_tier)

        discount_amount = base_price * (discount_pct / 100)
        final_price = base_price - discount_amount

        return {
            "base_price": base_price,
            "discount_percentage": discount_pct,
            "discount_amount": discount_amount,
            "final_price": final_price,
        }

    async def calculate_detailed_price(
        self, product: Dict, customer_tier: str, include_promotions: bool = True
    ) -> Dict[str, Any]:
        """Calcula precio detallado con todas las promociones"""
        pricing = await self.calculate_price(product, customer_tier)

        # Añadir promociones adicionales si aplican
        if include_promotions:
            # Simulación de promociones
            promotions = []

            # Black Friday
            if product.get("category") == "laptops":
                promotions.append({"name": "Black Friday Tech", "type": "percentage", "amount": "15%"})
                pricing["final_price"] *= 0.85

            pricing["discounts"] = promotions

        # Calcular ahorro total
        pricing["total_savings"] = pricing["base_price"] - pricing["final_price"]
        pricing["savings_percentage"] = (pricing["total_savings"] / pricing["base_price"]) * 100

        # Opciones de pago
        pricing["payment_options"] = [
            {"name": "Contado", "description": f"${pricing['final_price']:,.2f}"},
            {"name": "3 cuotas sin interés", "description": f"3x ${pricing['final_price'] / 3:,.2f}"},
        ]

        return pricing


class ProductComparisonTool:
    """Herramienta de comparación de productos"""

    def __init__(self, llm):
        self.llm = llm

    async def compare_products(self, products: List[Dict]) -> Dict[str, Any]:
        """Compara características de productos"""
        if len(products) < 2:
            raise ValueError("Se necesitan al menos 2 productos para comparar")

        product1, product2 = products[0], products[1]

        # Comparación básica de especificaciones
        comparison = {
            "product1": product1,
            "product2": product2,
            "specs_comparison": {},
            "advantages": {"product1": [], "product2": []},
        }

        # Comparar especificaciones comunes
        common_specs = set(product1.get("specs", {}).keys()) & set(product2.get("specs", {}).keys())

        for spec in common_specs:
            comparison["specs_comparison"][spec] = {
                "product1": product1["specs"][spec],
                "product2": product2["specs"][spec],
            }

        # Determinar ventajas (simplificado)
        if product1.get("price", 0) < product2.get("price", 0):
            comparison["advantages"]["product1"].append("Precio más económico")
        else:
            comparison["advantages"]["product2"].append("Mejor relación calidad-precio")

        # Recomendación basada en análisis
        comparison["recommendation"] = await self._generate_recommendation(comparison)

        return comparison

    async def _generate_recommendation(self, comparison: Dict) -> str:
        """Genera recomendación basada en la comparación"""
        # En producción esto usaría el LLM para análisis más sofisticado
        price_diff = abs(comparison["product1"]["price"] - comparison["product2"]["price"])

        if price_diff < 100:
            return "Ambos productos son excelentes opciones. La elección depende de tus preferencias específicas."
        else:
            cheaper = (
                comparison["product1"]
                if comparison["product1"]["price"] < comparison["product2"]["price"]
                else comparison["product2"]
            )
            return f"Si buscas la mejor relación precio-calidad, {cheaper['name']} es la opción recomendada."

