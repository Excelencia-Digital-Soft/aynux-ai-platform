from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class RecommendationAgent(BaseAgent):
    """Agente para manejar sugerencias y recomendaciones personalizadas"""

    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa solicitudes de recomendaciones y genera respuesta con AI"""

        # Analizar el perfil del cliente para recomendaciones
        customer_profile = self._analyze_customer_profile(customer, historial)

        # Obtener productos recomendados basados en el perfil
        recommendations = await self._get_personalized_recommendations(customer_profile, message_text)

        # Obtener productos complementarios si aplica
        complementary_products = await self._get_complementary_products(historial)

        # Construir contexto específico
        context_info = {
            "Perfil del cliente": customer_profile,
            "Productos recomendados": self._format_recommendations(recommendations),
            "Productos complementarios": self._format_complementary(complementary_products),
            "Presupuesto estimado": customer.get("budget_range", "No definido"),
        }

        context = self._build_context(customer, context_info)

        # Prompt específico para recomendaciones
        prompt = f"""
        Eres un asesor experto en tecnología de Conversa Shop haciendo recomendaciones personalizadas.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Analiza el perfil y necesidades del cliente para hacer recomendaciones precisas
        2. Sugiere productos que realmente aporten valor según su caso de uso
        3. Explica claramente por qué recomiendas cada producto
        4. Si hay productos complementarios, menciona cómo se potencian juntos
        5. Considera el presupuesto y sugiere opciones en diferentes rangos
        6. Usa comparaciones para ayudar en la decisión ("Si buscas X, este es ideal")
        7. Menciona beneficios específicos para el uso que le dará el cliente
        8. Incluye información sobre garantías y soporte
        
        ESTRATEGIA DE RECOMENDACIÓN:
        - Identifica la necesidad principal del cliente
        - Sugiere la mejor opción calidad-precio
        - Ofrece una alternativa premium y una económica
        - Recomienda accesorios o complementos que mejoren la experiencia
        
        FORMATO:
        - Usa títulos con **negritas** para cada recomendación
        - Lista los beneficios clave con viñetas
        - Incluye emojis relevantes (⭐ recomendado, 💎 premium, 💰 mejor precio)
        
        Genera recomendaciones personalizadas y convincentes que ayuden al cliente a decidir.
        """

        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.7)
        return response

    def _analyze_customer_profile(self, customer: Dict[str, Any], historial: str) -> str:
        """Analiza el perfil del cliente para personalizar recomendaciones"""
        profile_parts = []

        # Nivel de experiencia
        if customer["total_interactions"] > 5:
            profile_parts.append("Cliente recurrente con conocimiento de nuestros productos")
        else:
            profile_parts.append("Cliente nuevo explorando opciones")

        # Intereses previos
        if customer.get("interests"):
            profile_parts.append(f"Interesado en: {', '.join(customer['interests'])}")

        # Análisis del historial
        historial_lower = historial.lower()
        if "gaming" in historial_lower or "juegos" in historial_lower:
            profile_parts.append("Perfil gamer")
        elif "trabajo" in historial_lower or "oficina" in historial_lower:
            profile_parts.append("Uso profesional/empresarial")
        elif "estudiante" in historial_lower or "estudio" in historial_lower:
            profile_parts.append("Estudiante")

        # Sensibilidad al precio
        if "barato" in historial_lower or "económico" in historial_lower:
            profile_parts.append("Busca opciones económicas")
        elif "mejor" in historial_lower or "premium" in historial_lower:
            profile_parts.append("Busca calidad premium")

        return "; ".join(profile_parts)

    async def _get_personalized_recommendations(self, customer_profile: str, message_text: str):
        """Obtiene recomendaciones personalizadas según el perfil"""
        print("Recomendaciones - message_text: ", message_text)
        recommendations = []

        # Si es perfil gamer
        if "gamer" in customer_profile.lower():
            gaming_products = await self.product_service.get_products_by_category("laptops", "gaming", limit=2)
            recommendations.extend(gaming_products)

        # Si busca opciones económicas
        elif "económicas" in customer_profile.lower():
            budget_products = await self.product_service.get_products_by_price_range(0, 30000, limit=3)
            recommendations.extend(budget_products)

        # Si es uso profesional
        elif "profesional" in customer_profile.lower():
            work_products = await self.product_service.get_products_by_category("laptops", "work", limit=2)
            recommendations.extend(work_products)

        # Recomendaciones generales si no hay perfil específico
        if not recommendations:
            featured = await self.product_service.get_featured_products(limit=3)
            recommendations.extend(featured)

        return recommendations[:5]  # Limitar a 5 recomendaciones

    async def _get_complementary_products(self, historial: str):
        """Obtiene productos complementarios basados en el historial"""
        complementary = []

        # Si mencionó laptops, sugerir accesorios
        if "laptop" in historial.lower():
            peripherals = await self.product_service.get_products_by_category("peripherals", limit=2)
            complementary.extend(peripherals)

        # Si mencionó gaming, sugerir periféricos gaming
        if "gaming" in historial.lower():
            gaming_peripherals = await self.product_service.search_products("gaming mouse teclado", limit=2)
            complementary.extend(gaming_peripherals)

        return complementary[:3]

    def _format_recommendations(self, products: list) -> str:
        """Formatea las recomendaciones principales"""
        if not products:
            return "Buscando las mejores opciones..."

        formatted = []
        for i, product in enumerate(products):
            icon = "⭐" if i == 0 else "💎" if product.price > 100000 else "💰"

            prod_str = f"{icon} {product.name}"
            prod_str += f" - ${product.price:,.0f}"
            prod_str += f" | {product.specs[:80]}..."

            if hasattr(product, "featured") and product.featured:
                prod_str += " | DESTACADO"

            formatted.append(prod_str)

        return "\n".join(formatted)

    def _format_complementary(self, products: list) -> str:
        """Formatea productos complementarios"""
        if not products:
            return "Sin complementos específicos"

        formatted = []
        for product in products:
            formatted.append(f"+ {product.name} (${product.price:,.0f})")

        return "; ".join(formatted)

