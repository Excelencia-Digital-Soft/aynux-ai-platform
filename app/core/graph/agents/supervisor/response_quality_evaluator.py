"""
Response Quality Evaluator.

Evaluates the quality of agent responses across multiple dimensions.
Uses intelligent fallback detection and context-aware evaluation.
"""

import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ResponseCategory(Enum):
    """Categories for response quality classification."""

    COMPLETE_WITH_DATA = "complete_with_data"  # Contains specific information
    PARTIAL_INFO = "partial_info"  # Partial information provided
    FALLBACK_RESPONSE = "fallback_response"  # Generic, no real data
    ERROR_RESPONSE = "error_response"  # Error occurred
    REDIRECT_RESPONSE = "redirect_response"  # Only points elsewhere


class FallbackPatternDetector:
    """Detects fallback/generic responses that don't provide real value."""

    FALLBACK_PHRASES: dict[str, list[str]] = {
        "redirect": [
            "te recomiendo visitar",
            "visita la pagina",
            "visita el portal",
            "visitar nuestra",
            "contacta a",
            "contactar a",
            "comunicate con",
            "comunicarte con",
        ],
        "no_info": [
            "no encontre informacion",
            "no tengo informacion",
            "no dispongo de",
            "no cuento con",
            "no pude encontrar",
            "no tengo datos",
        ],
        "generic_offer": [
            "puedo ayudarte con",
            "estoy aqui para ayudarte",
            "en que mas puedo ayudarte",
        ],
    }

    def calculate_fallback_score(self, response: str) -> float:
        """
        Calculate fallback score from 0.0-1.0.

        Higher score means more fallback-like (less useful).
        """
        response_lower = response.lower()
        score = 0.0

        for pattern_type, phrases in self.FALLBACK_PHRASES.items():
            found = [p for p in phrases if p in response_lower]
            if pattern_type == "redirect" and found:
                score += 0.4
            elif pattern_type == "no_info" and found:
                score += 0.5
            elif pattern_type == "generic_offer" and found:
                score += 0.2

        return min(1.0, score)


class SpecificDataDetector:
    """Detects specific data in responses (names, numbers, dates)."""

    def detect_specific_data(self, response: str) -> dict[str, list[str]]:
        """
        Detect specific data elements in the response.

        Returns dict with detected names, numbers, dates, features.
        """
        found: dict[str, list[str]] = {
            "names": [],
            "numbers": [],
            "dates": [],
            "features": [],
        }

        # Proper names (consecutive capitalized words)
        found["names"] = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", response)

        # Numbers/prices
        found["numbers"] = re.findall(r"\$?\d+(?:[\.,]\d+)?", response)

        # Bullet points (features/list items)
        found["features"] = re.findall(r"[-•]\s*[^\n]+", response)

        return found

    def has_specific_data(self, found_data: dict[str, list[str]], query_type: str) -> bool:
        """
        Check if response has expected data for the query type.

        Args:
            found_data: Dictionary from detect_specific_data()
            query_type: Type of query (corporate, product, etc.)

        Returns:
            True if response contains expected specific data
        """
        if query_type == "corporate":
            # Corporate queries need names (CEO, director, etc.)
            return bool(found_data["names"])
        elif query_type in ("product", "products"):
            # Product queries often need prices/numbers
            return bool(found_data["numbers"])
        # Other query types don't require specific data
        return True


class ResponseQualityEvaluator:
    """
    Evaluates response quality across multiple dimensions.

    Responsibilities:
    - Evaluate completeness of responses
    - Evaluate relevance to user query
    - Evaluate clarity and readability
    - Evaluate helpfulness for the user
    - Calculate overall quality score
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        """
        Initialize the evaluator with quality thresholds.

        Args:
            thresholds: Dictionary of quality thresholds
        """
        self.thresholds = thresholds or {
            "response_completeness": 0.6,
            "response_relevance": 0.7,
            "task_completion": 0.8,
        }
        self.fallback_detector = FallbackPatternDetector()
        self.data_detector = SpecificDataDetector()

    async def evaluate(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
        conversation_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate the quality of an agent response.

        Uses intelligent fallback detection and context-aware evaluation
        to determine if re-routing would help.

        Args:
            user_message: Original user message
            agent_response: Agent's response
            agent_name: Name of the responding agent
            conversation_context: Full conversation context

        Returns:
            Dictionary with quality evaluation metrics including:
            - category: ResponseCategory for the response
            - suggested_action: "accept", "re_route", or "stop_retry"
            - fallback_score: How fallback-like the response is
            - rag_had_results: Whether RAG returned any results
        """
        # Extract RAG metrics from context
        # Note: ExcelenciaNode uses "has_results" (boolean), others might use "result_count"
        rag_metrics = conversation_context.get("rag_metrics", {})
        rag_had_results = rag_metrics.get("has_results", False) or rag_metrics.get("result_count", 0) > 0

        # Detect query type for context-aware evaluation
        query_type = self._detect_query_type(user_message)

        # Calculate fallback score
        fallback_score = self.fallback_detector.calculate_fallback_score(agent_response)

        # Detect specific data in response
        found_data = self.data_detector.detect_specific_data(agent_response)
        has_specific = self.data_detector.has_specific_data(found_data, query_type)

        # Categorize the response
        category = self._categorize_response(fallback_score, has_specific, query_type)

        # Calculate base scores (existing heuristics)
        completeness_score = self._evaluate_completeness(user_message, agent_response)
        relevance_score = self._evaluate_relevance(user_message, agent_response, agent_name)
        clarity_score = self._evaluate_clarity(agent_response)
        helpfulness_score = self._evaluate_helpfulness(agent_response)

        # Calculate weighted base score
        base_score = (
            completeness_score * 0.3
            + relevance_score * 0.3
            + clarity_score * 0.2
            + helpfulness_score * 0.2
        )

        # Adjust score based on category
        overall_score = self._adjust_by_category(base_score, category, fallback_score)

        # Determine suggested action
        retry_count = conversation_context.get("supervisor_retry_count", 0)
        agent_history = conversation_context.get("agent_history", [])
        suggested_action = self._determine_action(
            category, rag_had_results, retry_count, agent_history
        )

        logger.info(
            f"Quality evaluation: category={category.value}, score={overall_score:.2f}, "
            f"fallback={fallback_score:.2f}, rag_results={rag_had_results}, action={suggested_action}"
        )

        return {
            "overall_score": overall_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score,
            "clarity_score": clarity_score,
            "helpfulness_score": helpfulness_score,
            "agent_name": agent_name,
            "response_length": len(agent_response),
            # New intelligent evaluation fields
            "category": category.value,
            "suggested_action": suggested_action,
            "fallback_score": fallback_score,
            "rag_had_results": rag_had_results,
            "query_type": query_type,
            "found_specific_data": {
                "names": found_data.get("names", []),
                "has_specific": has_specific,
            },
            "evaluation_details": {
                "has_actionable_content": self._has_actionable_content(agent_response),
                "provides_specific_info": self._provides_specific_info(agent_response),
                "appropriate_tone": self._has_appropriate_tone(agent_response),
            },
            "conversation_context": conversation_context,
        }

    def _evaluate_completeness(self, user_message: str, agent_response: str) -> float:
        """Evaluate if the response is complete based on the user's question."""
        if not agent_response or len(agent_response) < 10:
            return 0.0

        response_length = len(agent_response)
        question_indicators = len(
            [
                word
                for word in ["qué", "cómo", "dónde", "cuándo", "por qué", "cuánto"]
                if word in user_message.lower()
            ]
        )

        # Penalize short responses for complex questions
        if question_indicators > 0 and response_length < 50:
            return 0.3

        # Reward responses with structured information
        if response_length > 100 and any(
            indicator in agent_response.lower()
            for indicator in ["información", "detalles", "proceso", "pasos"]
        ):
            return 0.9

        # Base score by length and structure
        base_score = min(0.8, response_length / 200)
        return base_score

    def _evaluate_relevance(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
    ) -> float:
        """Evaluate if the response is relevant to the user message."""
        if not agent_response:
            return 0.0

        user_words = set(user_message.lower().split())
        response_words = set(agent_response.lower().split())

        # Calculate word overlap
        common_words = user_words.intersection(response_words)
        word_overlap = len(common_words) / len(user_words) if user_words else 0

        # Consider if agent is appropriate for query type
        agent_relevance = self._check_agent_relevance(user_message, agent_name)

        return min(1.0, word_overlap * 0.6 + agent_relevance * 0.4)

    def _evaluate_clarity(self, agent_response: str) -> float:
        """Evaluate clarity and readability of the response."""
        if not agent_response:
            return 0.0

        sentence_count = len([s for s in agent_response.split(".") if len(s.strip()) > 5])
        avg_sentence_length = len(agent_response) / max(1, sentence_count)

        clarity_score = 0.8
        if avg_sentence_length > 150:
            clarity_score -= 0.3
        elif avg_sentence_length < 10:
            clarity_score -= 0.2

        # Reward clear structure
        if any(
            indicator in agent_response.lower()
            for indicator in ["primero", "segundo", "además", "finalmente"]
        ):
            clarity_score += 0.1

        return max(0.0, min(1.0, clarity_score))

    def _evaluate_helpfulness(self, agent_response: str) -> float:
        """Evaluate how helpful the response is for the user."""
        if not agent_response:
            return 0.0

        helpfulness_score = 0.5

        if self._has_actionable_content(agent_response):
            helpfulness_score += 0.2

        if self._provides_specific_info(agent_response):
            helpfulness_score += 0.2

        if self._has_appropriate_tone(agent_response):
            helpfulness_score += 0.1

        return min(1.0, helpfulness_score)

    def _has_actionable_content(self, agent_response: str) -> bool:
        """Check if response contains actionable content."""
        action_indicators = [
            "puedes",
            "debes",
            "recomiendo",
            "sugiero",
            "pasos",
            "proceso",
            "hacer",
            "seguir",
            "contactar",
            "verificar",
            "comprobar",
        ]
        return any(indicator in agent_response.lower() for indicator in action_indicators)

    def _provides_specific_info(self, agent_response: str) -> bool:
        """Check if response provides specific information."""
        specific_indicators = [
            "precio",
            "costo",
            "disponible",
            "stock",
            "características",
            "modelo",
            "marca",
            "especificaciones",
            "número",
            "fecha",
        ]
        return any(indicator in agent_response.lower() for indicator in specific_indicators)

    def _has_appropriate_tone(self, agent_response: str) -> bool:
        """Check if response has an appropriate tone."""
        positive_indicators = ["gracias", "gusto", "ayudar", "servicio", "atención"]
        negative_indicators = ["no puedo", "no sé", "imposible", "error"]

        positive_count = sum(
            1 for indicator in positive_indicators if indicator in agent_response.lower()
        )
        negative_count = sum(
            1 for indicator in negative_indicators if indicator in agent_response.lower()
        )

        return positive_count > negative_count

    def _check_agent_relevance(self, user_message: str, agent_name: str) -> float:
        """Check if the agent is relevant for the user message."""
        agent_keywords = {
            "product_agent": [
                "producto",
                "precio",
                "stock",
                "disponible",
                "características",
                "categoría",
                "tipo",
            ],
            "support_agent": ["problema", "ayuda", "soporte", "técnico", "falla"],
            "tracking_agent": ["pedido", "envío", "seguimiento", "entrega"],
            "invoice_agent": ["factura", "pago", "cobro", "recibo"],
            "promotions_agent": ["descuento", "oferta", "promoción", "cupón"],
            "excelencia_agent": [
                "excelencia",
                "erp",
                "demo",
                "módulo",
                "capacitación",
                "historia clínica",
                "hospital",
                "turnos",
                "obras sociales",
                "hotel",
                "ceo",
                "director",
                "fundador",
                "empresa",
                "quienes somos",
                "quién es",
                "quien es",
            ],
        }

        keywords = agent_keywords.get(agent_name, [])
        if not keywords:
            return 0.5  # Neutral for unmapped agents

        matches = sum(1 for keyword in keywords if keyword in user_message.lower())
        return min(1.0, matches / len(keywords) * 2)

    def _detect_query_type(self, user_message: str) -> str:
        """Detect query type from user message for context-aware evaluation."""
        message_lower = user_message.lower()

        # Corporate queries (CEO, directors, company info)
        corporate_keywords = [
            "ceo",
            "director",
            "fundador",
            "dueño",
            "propietario",
            "quien es",
            "quién es",
            "empresa",
            "quienes somos",
            "mision",
            "vision",
        ]
        if any(kw in message_lower for kw in corporate_keywords):
            return "corporate"

        # Product queries (prices, features)
        product_keywords = ["precio", "costo", "cuanto", "cuánto", "producto", "modulo", "módulo"]
        if any(kw in message_lower for kw in product_keywords):
            return "products"

        # Demo requests
        if any(kw in message_lower for kw in ["demo", "demostracion", "demostración", "prueba"]):
            return "demo"

        # Support queries
        if any(kw in message_lower for kw in ["problema", "error", "falla", "soporte", "ayuda"]):
            return "support"

        return "general"

    def _categorize_response(
        self,
        fallback_score: float,
        has_specific: bool,
        query_type: str,
    ) -> ResponseCategory:
        """
        Categorize response based on fallback detection and specific data.

        Args:
            fallback_score: Score from FallbackPatternDetector (0.0-1.0)
            has_specific: Whether response has expected specific data
            query_type: Type of user query

        Returns:
            ResponseCategory enum value
        """
        # High fallback score = generic response
        if fallback_score >= 0.6:
            return ResponseCategory.FALLBACK_RESPONSE

        # Medium fallback + no specific data = redirect-like
        if fallback_score >= 0.3 and not has_specific:
            return ResponseCategory.REDIRECT_RESPONSE

        # Corporate/product queries need specific data
        if query_type in ("corporate", "products") and not has_specific:
            return ResponseCategory.PARTIAL_INFO

        # Has specific data = complete
        if has_specific:
            return ResponseCategory.COMPLETE_WITH_DATA

        return ResponseCategory.PARTIAL_INFO

    def _adjust_by_category(
        self,
        base_score: float,
        category: ResponseCategory,
        fallback_score: float,
    ) -> float:
        """
        Adjust the base score based on response category.

        Penalizes fallback responses, rewards complete responses.
        """
        adjustments = {
            ResponseCategory.COMPLETE_WITH_DATA: +0.1,
            ResponseCategory.PARTIAL_INFO: 0.0,
            ResponseCategory.FALLBACK_RESPONSE: -0.3,
            ResponseCategory.REDIRECT_RESPONSE: -0.2,
            ResponseCategory.ERROR_RESPONSE: -0.4,
        }
        adjustment = adjustments.get(category, 0.0)
        return max(0.0, min(1.0, base_score + adjustment))

    def _determine_action(
        self,
        category: ResponseCategory,
        rag_had_results: bool,
        retry_count: int,
        agent_history: list[str],
    ) -> str:
        """
        Determine the suggested action based on evaluation.

        Returns one of:
        - "accept": Response is acceptable, complete the conversation
        - "re_route": Try a different agent
        - "stop_retry": Don't retry, re-routing won't help

        Logic:
        - Good response → accept
        - Max retries reached → accept (avoid infinite loops)
        - RAG empty → stop_retry (re-routing can't create data)
        - Same agent tried twice → stop_retry (avoid agent loops)
        - Fallback with RAG data → re_route (might help)
        """
        # Good response → accept
        if category == ResponseCategory.COMPLETE_WITH_DATA:
            return "accept"

        # Max retries reached (avoid infinite loops)
        if retry_count >= 2:
            logger.info(f"Max retries ({retry_count}) reached, accepting")
            return "accept"

        # RAG empty → re-routing won't create data magically
        if not rag_had_results:
            logger.info("RAG returned no results, stop retry (re-routing won't help)")
            return "stop_retry"

        # Same agent tried multiple times → avoid agent loops
        if len(agent_history) >= 2 and agent_history[-1] == agent_history[-2]:
            logger.info(f"Same agent ({agent_history[-1]}) tried twice, stop retry")
            return "stop_retry"

        # Fallback response with RAG data → re-routing might help
        if category == ResponseCategory.FALLBACK_RESPONSE and rag_had_results:
            logger.info("Fallback response with RAG data, suggesting re-route")
            return "re_route"

        # Default: accept what we have
        return "accept"
