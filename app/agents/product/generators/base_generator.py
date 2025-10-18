"""
Base abstract class for AI response generators.

All response generators must extend this class and implement the required methods.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ...integrations.ollama_integration import OllamaIntegration
from ..models import UserIntent


class BaseResponseGenerator(ABC):
    """
    Abstract base class for AI-powered response generators.

    Each generator is specialized for a specific search source (pgvector, ChromaDB, database)
    and generates responses optimized for that source's result characteristics.
    """

    def __init__(self, ollama: OllamaIntegration, config: Dict[str, Any]):
        """
        Initialize response generator.

        Args:
            ollama: OllamaIntegration instance for AI inference
            config: Generator-specific configuration
        """
        self.ollama = ollama
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def generate_response(
        self, products: List[Dict[str, Any]], user_message: str, intent: UserIntent, search_metadata: Dict[str, Any]
    ) -> str:
        """
        Generate AI-powered response for products.

        This is the main method that creates a natural language response
        based on the search results and user context.

        Args:
            products: List of product dictionaries from search
            user_message: Original user message
            intent: Analyzed user intent
            search_metadata: Additional metadata from search (similarity scores, etc.)

        Returns:
            Generated response text

        Raises:
            Exception: If AI generation fails critically
        """
        pass

    @abstractmethod
    def get_fallback_response(self, products: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        """
        Generate fallback response when AI fails.

        This method provides a simple formatted response without AI
        to ensure the user always gets a response even if AI fails.

        Args:
            products: List of product dictionaries
            metadata: Search metadata

        Returns:
            Formatted fallback response text
        """
        pass

    def _build_prompt(
        self, products: List[Dict[str, Any]], message: str, intent: UserIntent, metadata: Dict[str, Any]
    ) -> str:
        """
        Build AI prompt (template method pattern).

        Subclasses can override this to customize prompt structure
        based on their specific search source.

        Args:
            products: Product list
            message: User message
            intent: User intent
            metadata: Search metadata

        Returns:
            Formatted prompt for AI
        """
        # Default implementation - subclasses should override
        product_info = self._format_products_for_prompt(products)
        intent_info = self._format_intent_for_prompt(intent)

        prompt = f"""# E-COMMERCE PRODUCT SEARCH ASSISTANT

## USER MESSAGE
"{message}"

## USER INTENT ANALYSIS
{intent_info}

## LANGUAGE DETECTION & RESPONSE REQUIREMENT
IMPORTANT: Detect the language of the user's query and respond in the SAME language.
- If Spanish → Respond in Spanish
- If English → Respond in English
- If Portuguese → Respond in Portuguese
- Default: Spanish

## FOUND PRODUCTS
{product_info}

## SEARCH METADATA
{self._format_metadata_for_prompt(metadata)}

## INSTRUCTIONS
Generate a natural, conversational response that:
1. Highlights the most relevant products (top 3-5)
2. Includes key details: name, brand, price, stock status
3. Uses natural language and friendly tone
4. Maximum 6 lines, concise but informative
5. Includes relevant emojis moderately (1-3 max)
6. Consider user intent (category, brand, price range) when emphasizing products

Generate your response now:"""

        return prompt

    def _format_products_for_prompt(self, products: List[Dict[str, Any]]) -> str:
        """
        Format products for inclusion in prompt.

        Args:
            products: List of product dictionaries

        Returns:
            Formatted product information string
        """
        if not products:
            return "No products found."

        product_lines = []
        for i, product in enumerate(products[:10], 1):
            name = product.get("name", "Unknown")
            brand = product.get("brand", {}).get("name", "N/A")
            price = product.get("price", 0)
            stock = product.get("stock", 0)
            similarity = product.get("similarity_score", 0)

            line = f"{i}. **{name}**"
            if brand and brand != "N/A":
                line += f" ({brand})"
            line += f" - ${price:,.2f}"
            line += f" - {'✅ In stock' if stock > 0 else '❌ Out of stock'}"
            if similarity > 0:
                line += f" - Relevance: {similarity:.2f}"

            product_lines.append(line)

        return "\n".join(product_lines)

    def _format_metadata_for_prompt(self, metadata: Dict[str, Any]) -> str:
        """
        Format metadata for inclusion in prompt.

        Args:
            metadata: Metadata dictionary

        Returns:
            Formatted metadata string
        """
        if not metadata:
            return "No additional metadata"

        meta_lines = []
        for key, value in metadata.items():
            if value is not None:
                meta_lines.append(f"- {key}: {value}")

        return "\n".join(meta_lines) if meta_lines else "No additional metadata"

    def _format_intent_for_prompt(self, intent: UserIntent) -> str:
        """
        Format user intent for inclusion in prompt.

        Args:
            intent: UserIntent object

        Returns:
            Formatted intent information string
        """
        intent_lines = [f"- Intent: {intent.intent}"]

        if intent.search_terms:
            intent_lines.append(f"- Search terms: {', '.join(intent.search_terms)}")

        if intent.category:
            intent_lines.append(f"- Category filter: {intent.category}")

        if intent.brand:
            intent_lines.append(f"- Brand preference: {intent.brand}")

        if intent.price_min is not None or intent.price_max is not None:
            price_range = []
            if intent.price_min is not None:
                price_range.append(f"min ${intent.price_min:,.2f}")
            if intent.price_max is not None:
                price_range.append(f"max ${intent.price_max:,.2f}")
            intent_lines.append(f"- Price range: {' - '.join(price_range)}")

        if intent.specific_product:
            intent_lines.append(f"- Looking for: {intent.specific_product}")

        # Boolean flags
        flags = []
        if intent.wants_stock_info:
            flags.append("stock availability")
        if intent.wants_featured:
            flags.append("featured products")
        if intent.wants_sale:
            flags.append("sale/discounts")

        if flags:
            intent_lines.append(f"- Special interests: {', '.join(flags)}")

        return "\n".join(intent_lines)

    async def _invoke_llm(self, prompt: str, temperature: float = 0.7, model: str = "llama3.1") -> str:
        """
        Invoke LLM with prompt.

        Args:
            prompt: Formatted prompt
            temperature: LLM temperature (0.0-1.0)
            model: Model name

        Returns:
            AI-generated text

        Raises:
            Exception: If LLM invocation fails
        """
        llm = self.ollama.get_llm(temperature=temperature, model=model)
        response = await llm.ainvoke(prompt)

        # Handle response.content which can be string or list
        content = response.content
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            # Join list elements and strip
            return " ".join(str(item) for item in content).strip()
        else:
            # Fallback: convert to string
            return str(content).strip()

    def get_config(self) -> Dict[str, Any]:
        """
        Get current generator configuration.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update generator configuration.

        Args:
            config: New configuration values (merged with existing)
        """
        self.config.update(config)
        self.logger.info(f"Configuration updated for {self.__class__.__name__}")

    def get_trace_metadata(self) -> Dict[str, Any]:
        """
        Get metadata for LangSmith tracing.

        Returns:
            Dictionary with trace metadata
        """
        return {
            "generator_class": self.__class__.__name__,
            "config": self.get_config(),
        }

