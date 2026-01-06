"""
AI Response Generator

Generates natural language responses using AI for product queries.
Single Responsibility: AI-powered response generation.
"""

import logging
from typing import Any

from app.integrations.llm import VllmLLM
from app.prompts.product_response import (
    build_no_results_prompt,
    build_product_response_prompt,
)

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

    Uses vLLM to generate natural, context-aware responses.
    Follows Single Responsibility Principle.
    """

    def __init__(
        self,
        llm: VllmLLM | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize AI response generator.

        Args:
            llm: VllmLLM instance
            config: Configuration dict
        """
        self.llm = llm or VllmLLM()
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

            # Format products as cards for frontend
            product_cards = self.formatter.format_products_as_cards(context.products)

            # Format products as markdown for AI context
            formatted_products = self.formatter.format_products_as_markdown(context.products)

            # Generate AI response
            response_text = await self._generate_ai_text(context, formatted_products)

            return GeneratedResponse(
                text=response_text,
                response_type="ai_generated",
                metadata={
                    "product_count": context.product_count,
                    "source": context.search_metadata.get("source", "unknown"),
                    "temperature": self.temperature,
                    "display_type": "product_cards",
                    "products": product_cards,
                },
                requires_followup=False,
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            # Fallback to formatted products if AI fails
            return self._generate_fallback_response(context)

    async def _generate_ai_text(self, context: ResponseContext, formatted_products: str) -> str:
        """
        Generate AI text using vLLM.

        Args:
            context: Response context
            formatted_products: Pre-formatted product list

        Returns:
            AI-generated response text
        """
        # Build AI prompt
        prompt = await self._build_prompt(context, formatted_products)

        # Get LLM and generate response
        llm_instance = self.llm.get_llm(
            temperature=self.temperature,
            num_predict=self.max_tokens,
        )
        response = await llm_instance.ainvoke(prompt)

        # Handle response content (can be str or list)
        content = response.content
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            return " ".join(str(item) for item in content).strip()
        else:
            return str(content).strip()

    async def _build_prompt(self, context: ResponseContext, formatted_products: str) -> str:
        """
        Build prompt for AI generation.

        Args:
            context: Response context
            formatted_products: Formatted product list

        Returns:
            Complete prompt for AI
        """
        intent = context.intent_analysis.get("intent", "search_products")

        # Analyze stock availability
        products_with_stock = sum(1 for p in context.products if p.get("stock", 0) > 0)
        products_without_stock = context.product_count - products_with_stock

        # Use external prompt builder (SRP: prompts separated from logic)
        return await build_product_response_prompt(
            user_query=context.user_query,
            intent=intent,
            product_count=context.product_count,
            formatted_products=formatted_products,
            products_with_stock=products_with_stock,
            products_without_stock=products_without_stock,
        )

    async def _generate_no_results_response(self, context: ResponseContext) -> GeneratedResponse:
        """
        Generate response when no products found.

        Args:
            context: Response context

        Returns:
            Generated response
        """
        # Use external prompt builder (SRP: prompts separated from logic)
        prompt = await build_no_results_prompt(context.user_query)

        try:
            # Get LLM and generate response
            llm_instance = self.llm.get_llm(
                temperature=self.temperature,
                num_predict=300,
            )
            response = await llm_instance.ainvoke(prompt)

            # Handle response content (can be str or list)
            content = response.content
            if isinstance(content, str):
                response_text = content.strip()
            elif isinstance(content, list):
                response_text = " ".join(str(item) for item in content).strip()
            else:
                response_text = str(content).strip()

            return GeneratedResponse(
                text=response_text,
                response_type="ai_no_results",
                metadata={"reason": "no_products_found"},
                requires_followup=True,
            )

        except Exception as e:
            logger.error(f"Error generating no-results response: {e}")
            # Use formatter as fallback
            fallback_text = self.formatter.format_no_results_message(context.intent_analysis)
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
        """Check if VllmLLM is available."""
        try:
            return await self.llm.health_check()
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
