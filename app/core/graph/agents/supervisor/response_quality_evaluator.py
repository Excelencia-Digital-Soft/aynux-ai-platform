"""
Response Quality Evaluator.

Evaluates the quality of agent responses across multiple dimensions.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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

    async def evaluate(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
        conversation_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate the quality of an agent response.

        Args:
            user_message: Original user message
            agent_response: Agent's response
            agent_name: Name of the responding agent
            conversation_context: Full conversation context

        Returns:
            Dictionary with quality evaluation metrics
        """
        completeness_score = self._evaluate_completeness(user_message, agent_response)
        relevance_score = self._evaluate_relevance(user_message, agent_response, agent_name)
        clarity_score = self._evaluate_clarity(agent_response)
        helpfulness_score = self._evaluate_helpfulness(agent_response)

        # Calculate weighted overall score
        overall_score = (
            completeness_score * 0.3
            + relevance_score * 0.3
            + clarity_score * 0.2
            + helpfulness_score * 0.2
        )

        return {
            "overall_score": overall_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score,
            "clarity_score": clarity_score,
            "helpfulness_score": helpfulness_score,
            "agent_name": agent_name,
            "response_length": len(agent_response),
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
            ],
        }

        keywords = agent_keywords.get(agent_name, [])
        if not keywords:
            return 0.5  # Neutral for unmapped agents

        matches = sum(1 for keyword in keywords if keyword in user_message.lower())
        return min(1.0, matches / len(keywords) * 2)
