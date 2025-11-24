"""
Intent analysis for product queries.

Extracts user intent from natural language messages using AI.
"""

import logging
from typing import Optional

from app.agents.integrations.ollama_integration import OllamaIntegration
from app.utils import extract_json_from_text

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

    INTENT_ANALYSIS_PROMPT = """# USER MESSAGE
"{message}"

# INSTRUCTIONS
You are analyzing a user's product inquiry for an e-commerce system. Extract the user's intent and respond with JSON:

{{
  "intent": "show_general_catalog|search_specific_products|search_by_category|search_by_brand|search_by_price|get_product_details",
  "search_terms": ["specific", "product", "terms"],
  "category": "category_name_or_null",
  "brand": "brand_name_or_null",
  "price_min": float_or_null,
  "price_max": float_or_null,
  "specific_product": "exact_product_name_or_null",
  "wants_stock_info": boolean,
  "wants_featured": boolean,
  "wants_sale": boolean,
  "action_needed": "show_featured|search_products|search_category|search_brand|search_price",
  "confidence": float_0_to_1,
  "user_emotion": "neutral|excited|frustrated|urgent|curious|disappointed"
}}

INTENT ANALYSIS:
- show_general_catalog: User asks what products are available, general catalog inquiry ("what products do you have", "show me your products")
- search_specific_products: User wants specific products ("show me laptops", "I need a phone")
- search_by_category: User mentions a specific category
- search_by_brand: User mentions a specific brand
- search_by_price: User mentions price range
- get_product_details: User asks about a specific product

For search_terms, only include meaningful product-related words, not filler words.

CONFIDENCE SCORE (0.0-1.0):
- 0.9-1.0: Very clear intent with specific details (brand, model, exact product name)
- 0.7-0.9: Clear intent with some details (category, general product type)
- 0.5-0.7: Moderate clarity, general inquiry
- 0.3-0.5: Ambiguous intent, unclear what user wants
- 0.0-0.3: Very unclear or off-topic message

EMOTION ANALYSIS:
Detect the user's emotional state from their message tone:
- neutral: Calm, matter-of-fact inquiry ("show me laptops")
- excited: Enthusiastic, eager to buy ("I need this now!", "wow!")
- frustrated: Annoyed, having trouble finding what they need ("I can't find anything", "this is difficult")
- urgent: Time-sensitive need ("I need it today", "ASAP", "quickly")
- curious: Exploring options, browsing ("what do you have?", "just looking")
- disappointed: Previous negative experience or unmet expectations ("still not what I want")"""

    def __init__(
        self,
        ollama: OllamaIntegration,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ):
        """
        Initialize intent analyzer.

        Args:
            ollama: OllamaIntegration instance for AI inference
            temperature: LLM temperature for intent analysis (0.0-1.0)
            model: Optional model name override
        """
        self.ollama = ollama
        self.temperature = temperature
        self.model = model
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
        prompt = self.INTENT_ANALYSIS_PROMPT.format(message=message)

        # Default fallback intent
        default_intent_dict = self.DEFAULT_INTENT_VALUES.copy()
        default_intent_dict["search_terms"] = message.split()  # Use message words as fallback

        try:
            # Invoke LLM
            llm = self.ollama.get_llm(temperature=self.temperature, model=self.model)
            response = await llm.ainvoke(prompt)

            # Extract JSON from response
            required_keys = ["intent"]  # Minimum required key
            extracted_json = extract_json_from_text(
                response.content, default=default_intent_dict, required_keys=required_keys
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
