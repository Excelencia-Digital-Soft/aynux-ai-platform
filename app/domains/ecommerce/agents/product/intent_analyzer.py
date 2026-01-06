"""
Intent analysis for product queries.

Extracts user intent from natural language messages using AI.
"""

import logging
from typing import Optional

from app.integrations.llm import VllmLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.utils import extract_json_from_text
from app.prompts.manager import PromptManager

from .models import UserIntent

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    """
    Analyzes user intent using AI to extract structured information.

    Applies Single Responsibility Principle by focusing solely on intent analysis,
    separating this concern from search and response generation.
    """

    DEFAULT_INTENT_VALUES = {
        "intent": "search_general",
        "search_terms": [],
        "category": None,
        "brand": None,
        "price_min": None,
        "price_max": None,
        "specific_product": None,
        "wants_stock_info": False,
        "wants_featured": False,
        "wants_sale": False,
        "action_needed": "search_products",
        "confidence": 0.5,  # Low confidence for default fallback
        "user_emotion": "neutral",  # Default emotion
    }

    def __init__(
        self,
        llm: VllmLLM,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ):
        """
        Initialize intent analyzer.

        Args:
            llm: VllmLLM instance for AI inference
            temperature: LLM temperature for intent analysis (0.0-1.0)
            model: Optional specific model to use for intent analysis.
        """
        self.llm = llm
        self.temperature = temperature
        self.model = model
        self.prompt_manager = PromptManager()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def analyze_intent(self, message: str) -> UserIntent:
        """
        Analyze user intent from natural language message.

        Args:
            message: User's natural language product query

        Returns:
            UserIntent with structured intent analysis

        Raises:
            Exception: If AI analysis fails critically (falls back to default intent)
        """
        self.logger.info(f"Analyzing intent for message: '{message[:50]}...'")

        # Build prompt
        prompt = await self.prompt_manager.get_prompt(
            "ecommerce.intent_analyzer.product_query",
            variables={"message": message}
        )

        # Default fallback intent
        default_intent_dict = self.DEFAULT_INTENT_VALUES.copy()
        default_intent_dict["search_terms"] = message.split()  # Use message words as fallback

        try:
            # Invoke LLM
            llm_instance = self.llm.get_llm(
                complexity=ModelComplexity.SIMPLE,
                temperature=self.temperature,
                model=self.model,
            )
            response = await llm_instance.ainvoke(prompt)

            # Extract JSON from response
            required_keys = ["intent"]  # Minimum required key
            response_text = response.content if isinstance(response.content, str) else str(response.content)
            extracted_json = extract_json_from_text(
                response_text, default=default_intent_dict, required_keys=required_keys
            )

            # Ensure all expected keys are present with defaults
            if extracted_json and isinstance(extracted_json, dict):
                for key, value in default_intent_dict.items():
                    if key not in extracted_json:
                        extracted_json[key] = value

                # Calculate confidence as fallback if not provided by LLM
                if "confidence" not in extracted_json or extracted_json["confidence"] is None:
                    extracted_json["confidence"] = self._calculate_confidence(extracted_json)
                    self.logger.debug(f"Calculated fallback confidence: {extracted_json['confidence']:.2f}")

                # Convert to UserIntent dataclass
                intent = UserIntent.from_dict(extracted_json)
                self.logger.info(f"Intent analysis successful: {intent.intent} (confidence: {intent.confidence:.2f})")
                return intent
            else:
                self.logger.warning("Failed to extract JSON from LLM response, using default intent")
                return UserIntent.from_dict(default_intent_dict)

        except Exception as e:
            self.logger.error(f"Error analyzing product intent: {str(e)}")
            return UserIntent.from_dict(default_intent_dict)

    def get_default_intent(self, message: str) -> UserIntent:
        """
        Get default intent for a message when AI analysis is unavailable.

        Args:
            message: User's natural language product query

        Returns:
            UserIntent with default values and message words as search_terms
        """
        default_dict = self.DEFAULT_INTENT_VALUES.copy()
        default_dict["search_terms"] = message.split()
        return UserIntent.from_dict(default_dict)

    def _calculate_confidence(self, intent_data: dict) -> float:
        """
        Calculate confidence score based on intent analysis completeness.

        This is a fallback method when LLM doesn't provide confidence.
        Scores based on:
        - Presence of specific details (brand, category, specific_product)
        - Number of search terms
        - Clarity of action needed

        Args:
            intent_data: Extracted intent data

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 0.5  # Base confidence

        # Boost for specific details
        if intent_data.get("specific_product"):
            confidence += 0.3  # Very specific
        elif intent_data.get("brand"):
            confidence += 0.2  # Brand specified
        elif intent_data.get("category"):
            confidence += 0.15  # Category specified

        # Boost for price range (indicates specific intent)
        if intent_data.get("price_min") or intent_data.get("price_max"):
            confidence += 0.1

        # Boost for number of search terms (more terms = clearer intent)
        search_terms = intent_data.get("search_terms", [])
        if len(search_terms) >= 3:
            confidence += 0.1
        elif len(search_terms) >= 1:
            confidence += 0.05

        # Boost for specific flags (indicates clear user intent)
        if intent_data.get("wants_stock_info") or intent_data.get("wants_featured") or intent_data.get("wants_sale"):
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)

    def update_temperature(self, temperature: float) -> None:
        """
        Update LLM temperature for intent analysis.

        Args:
            temperature: New temperature value (0.0-1.0)

        Raises:
            ValueError: If temperature is out of range
        """
        if not 0.0 <= temperature <= 1.0:
            raise ValueError(f"Temperature must be between 0.0 and 1.0, got {temperature}")

        self.temperature = temperature
        self.logger.info(f"Temperature updated to {temperature}")
