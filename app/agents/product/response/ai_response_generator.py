"""
AI Response Generator

Generates natural language responses using AI for product queries.
Single Responsibility: AI-powered response generation.
"""

import logging
from typing import Any, Dict, List, Optional

from app.agents.integrations.ollama_integration import OllamaIntegration

from .base_response_generator import (
    BaseResponseGenerator,
    GeneratedResponse,
    ResponseContext,
)
from .product_formatter import ProductFormatter

logger = logging.getLogger(__name__)


class AIResponseGenerator(BaseResponseGenerator):
    """
    Generates AI-powered responses for product queries.

    Uses Ollama LLM to generate natural, context-aware responses.
    Follows Single Responsibility Principle.
    """

    def __init__(
        self,
        ollama: Optional[OllamaIntegration] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize AI response generator.

        Args:
            ollama: Ollama integration instance
            config: Configuration dict
        """
        self.ollama = ollama or OllamaIntegration()
        self.config = config or {}
        self.formatter = ProductFormatter(config)

        # AI configuration
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 500)

    @property
    def name(self) -> str:
        """Get generator name."""
        return "ai"

    @property
    def priority(self) -> int:
        """AI generator has highest priority."""
        return 10

    async def generate(self, context: ResponseContext) -> GeneratedResponse:
        """
        Generate AI response from context.

        Args:
            context: Response context with products and metadata

        Returns:
            Generated response with AI text
        """
        try:
            if not context.has_products:
                return await self._generate_no_results_response(context)

            # Format products for AI
            formatted_products = self.formatter.format_multiple_products(
                context.products
            )

            # Generate AI response
            response_text = await self._generate_ai_text(context, formatted_products)

            return GeneratedResponse(
                text=response_text,
                response_type="ai_generated",
                metadata={
                    "product_count": context.product_count,
                    "source": context.search_metadata.get("source", "unknown"),
                    "temperature": self.temperature,
                },
                requires_followup=False,
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            # Fallback to formatted products if AI fails
            return self._generate_fallback_response(context)

    async def _generate_ai_text(
        self, context: ResponseContext, formatted_products: str
    ) -> str:
        """
        Generate AI text using Ollama.

        Args:
            context: Response context
            formatted_products: Pre-formatted product list

        Returns:
            AI-generated response text
        """
        # Build AI prompt
        prompt = self._build_prompt(context, formatted_products)

        # Generate response
        response = await self.ollama.generate(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return response.strip()

    def _build_prompt(self, context: ResponseContext, formatted_products: str) -> str:
        """
        Build prompt for AI generation.

        Args:
            context: Response context
            formatted_products: Formatted product list

        Returns:
            Complete prompt for AI
        """
        intent = context.intent_analysis.get("intent", "search_products")
        search_terms = context.intent_analysis.get("search_terms", [])
        category = context.intent_analysis.get("category")
        brand = context.intent_analysis.get("brand")

        prompt = f"""# CONTEXTO
Eres un asistente de e-commerce ayudando a un cliente con su búsqueda de productos.

# CONSULTA DEL USUARIO
"{context.user_query}"

# INTENCIÓN DETECTADA
{intent}

# PRODUCTOS ENCONTRADOS ({context.product_count})
{formatted_products}

# INSTRUCCIONES
1. Genera una respuesta natural y útil
2. Destaca los productos más relevantes
3. Menciona características clave (precio, stock, marca)
4. Usa un tono amigable y profesional
5. Ofrece ayuda adicional si es necesario
6. Mantén la respuesta concisa (máximo 3-4 párrafos)
7. Usa emojis cuando sea apropiado

# RESPUESTA"""

        return prompt

    async def _generate_no_results_response(
        self, context: ResponseContext
    ) -> GeneratedResponse:
        """
        Generate response when no products found.

        Args:
            context: Response context

        Returns:
            Generated response
        """
        prompt = f"""# CONTEXTO
Eres un asistente de e-commerce. El cliente buscó productos pero no se encontraron resultados.

# CONSULTA DEL USUARIO
"{context.user_query}"

# INSTRUCCIONES
1. Expresa empatía por no encontrar resultados
2. Sugiere alternativas o búsquedas similares
3. Ofrece ayuda para refinar la búsqueda
4. Mantén un tono positivo y servicial
5. Pregunta si hay algo más en lo que puedas ayudar

# RESPUESTA"""

        try:
            response_text = await self.ollama.generate(
                prompt=prompt, temperature=self.temperature, max_tokens=300
            )

            return GeneratedResponse(
                text=response_text.strip(),
                response_type="ai_no_results",
                metadata={"reason": "no_products_found"},
                requires_followup=True,
            )

        except Exception as e:
            logger.error(f"Error generating no-results response: {e}")
            # Use formatter as fallback
            fallback_text = self.formatter.format_no_results_message(
                context.intent_analysis
            )
            return GeneratedResponse(
                text=fallback_text,
                response_type="fallback_no_results",
                metadata={"error": str(e)},
                requires_followup=True,
            )

    def _generate_fallback_response(self, context: ResponseContext) -> GeneratedResponse:
        """
        Generate fallback response when AI fails.

        Args:
            context: Response context

        Returns:
            Fallback response with formatted products
        """
        intro = (
            "Encontré estos productos que podrían interesarte:\n\n"
            if context.has_products
            else "No encontré productos con esos criterios.\n\n"
        )

        product_text = (
            self.formatter.format_multiple_products(context.products)
            if context.has_products
            else self.formatter.format_no_results_message(context.intent_analysis)
        )

        return GeneratedResponse(
            text=intro + product_text,
            response_type="fallback",
            metadata={"reason": "ai_generation_failed"},
            requires_followup=False,
        )

    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            return await self.ollama.health_check()
        except Exception as e:
            logger.error(f"AI response generator health check failed: {e}")
            return False

    async def can_generate(self, context: ResponseContext) -> bool:
        """
        Check if AI generation is appropriate for context.

        Args:
            context: Response context

        Returns:
            True if AI generation is suitable
        """
        # AI generation is suitable for most contexts
        # but may skip for very large product lists
        return context.product_count <= 50
