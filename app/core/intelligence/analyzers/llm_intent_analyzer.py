"""LLM-based intent analysis using Ollama.

Extracted from IntentRouter to follow Single Responsibility Principle.
Primary analyzer that uses AI for intent detection.
"""

import asyncio
import json
import logging
import os
from typing import Any

from app.core.intelligence.cache.intent_cache import IntentCache
from app.core.intelligence.metrics.router_metrics import RouterMetrics
from app.core.intelligence.validators.intent_validator import IntentValidator
from app.core.schemas import get_valid_intents
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.intent_analyzer_prompt import get_build_llm_prompt, get_system_prompt
from app.utils import extract_json_from_text

logger = logging.getLogger(__name__)

# Configuration constants
INTENT_LLM_TIMEOUT = float(os.getenv("INTENT_LLM_TIMEOUT", "60.0"))
INTENT_LLM_TEMPERATURE = 0.3


class LLMIntentAnalyzer:
    """LLM-based intent analysis using Ollama.

    Primary analyzer that uses AI for accurate intent detection.
    Falls back to other analyzers if confidence is too low.

    Features:
    - Ollama LLM integration
    - Response caching
    - Intent validation and mapping
    - Timeout handling
    """

    def __init__(
        self,
        ollama: Any,
        cache: IntentCache,
        validator: IntentValidator,
        metrics: RouterMetrics,
    ):
        """Initialize LLM analyzer.

        Args:
            ollama: OllamaLLM instance for LLM calls
            cache: IntentCache for caching results
            validator: IntentValidator for validation and mapping
            metrics: RouterMetrics for tracking
        """
        self._ollama = ollama
        self._cache = cache
        self._validator = validator
        self._metrics = metrics

    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze message using LLM.

        Args:
            message: User message to analyze
            context: Optional context with customer_data, conversation_data

        Returns:
            Intent result dict
        """
        state_dict = context or {}

        logger.debug(f"LLM analysis for: {message[:30]}...")

        # Check cache first
        cache_key = self._cache.get_key(message, state_dict)
        if cached_result := self._cache.get(cache_key):
            logger.info(f"Intent cache hit: {cached_result['primary_intent']}")
            return cached_result

        # Cache miss - call LLM
        self._metrics.increment_llm_calls()

        system_prompt = await get_system_prompt()
        user_prompt = await get_build_llm_prompt(message, state_dict)
        response_text = ""

        try:
            response_text = await asyncio.wait_for(
                self._ollama.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    complexity=ModelComplexity.SIMPLE,
                    temperature=INTENT_LLM_TEMPERATURE,
                ),
                timeout=INTENT_LLM_TIMEOUT,
            )

            # Extract JSON from response
            result = extract_json_from_text(
                response_text,
                default={
                    "intent": "fallback",
                    "confidence": 0.4,
                    "reasoning": "Could not parse LLM response",
                },
                required_keys=["intent"],
            )

            if not result or not isinstance(result, dict):
                logger.warning("Failed to extract JSON from LLM response")
                return self._create_fallback_result("Failed to parse LLM response")

            logger.debug(f"LLM response: {json.dumps(result)}")

            # Validate intent
            valid_intents = set(get_valid_intents()) | {"follow_up"}
            validated_intent, _, validation_reason = self._validator.validate_and_map_intent(
                result["intent"],
                valid_intents,
            )

            # Update result with validated intent
            if validated_intent != result["intent"]:
                result["intent"] = validated_intent
                if validated_intent == "fallback":
                    result["confidence"] = 0.4
                    result["reasoning"] = validation_reason

            # Handle follow_up intent
            conversation_data = state_dict.get("conversation_data", {})
            if result["intent"] == "follow_up":
                target_agent = self._validator.handle_follow_up_intent(conversation_data)
            else:
                target_agent = self._validator.map_intent_to_agent(result["intent"])

            # Create final result
            final_result = {
                "primary_intent": result["intent"],
                "intent": result["intent"],
                "confidence": result.get("confidence", 0.7),
                "entities": result.get("entities", {}),
                "requires_handoff": False,
                "target_agent": target_agent,
                "method": self.get_method_name(),
                "reasoning": result.get("reasoning", "LLM analysis"),
            }

            # Cache result
            self._cache.set(cache_key, final_result)

            logger.info(
                f"LLM Intent: {result['intent']} "
                f"(confidence: {result.get('confidence', 0):.2f}) - "
                f"{result.get('reasoning', '')}"
            )

            return final_result

        except asyncio.TimeoutError:
            logger.error(f"LLM analysis timed out after {INTENT_LLM_TIMEOUT}s")
            return self._create_fallback_result("LLM timeout")

        except KeyError as e:
            logger.error(f"Missing key in LLM response: {e}. Raw: '{response_text}'")
            return self._create_fallback_result(f"Missing key: {e}")

        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error"
            logger.error(
                f"LLM analysis error: {error_msg} | "
                f"Message: '{message[:100]}...' | "
                f"Response: '{response_text[:200]}...'"
            )
            return self._create_fallback_result(error_msg)

    def _create_fallback_result(self, reason: str) -> dict[str, Any]:
        """Create fallback result for error cases.

        Args:
            reason: Reason for fallback

        Returns:
            Fallback intent result
        """
        self._metrics.increment_fallback_calls()
        return {
            "primary_intent": "fallback",
            "intent": "fallback",
            "confidence": 0.3,
            "entities": {},
            "requires_handoff": False,
            "target_agent": "fallback_agent",
            "method": self.get_method_name(),
            "reasoning": f"Fallback: {reason}",
        }

    def get_method_name(self) -> str:
        """Return analyzer method name for metrics."""
        return "ollama_llm"
