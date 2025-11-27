"""
Evaluators Module.

Custom evaluators for LangSmith integration in Aynux.

Components:
- RoutingEvaluators: Intent routing and agent selection accuracy
- QualityEvaluators: Response quality and relevance
- BusinessEvaluators: Satisfaction, conversion, and task completion
- LanguageEvaluators: Language detection and localization
- AynuxEvaluators: Facade for comprehensive evaluation
"""

import logging
from datetime import datetime
from typing import Any

from langsmith.schemas import Example, Run

try:
    from langsmith.evaluation import LangSmithRunEvaluator
except ImportError:

    class LangSmithRunEvaluator:
        def __init__(self, evaluator_func):
            self.evaluator_func = evaluator_func


from app.config.langsmith_config import get_tracer
from app.evaluation.evaluators.business_evaluators import BusinessEvaluators
from app.evaluation.evaluators.language_evaluators import LanguageEvaluators
from app.evaluation.evaluators.models import EvaluationResult
from app.evaluation.evaluators.quality_evaluators import QualityEvaluators
from app.evaluation.evaluators.routing_evaluators import RoutingEvaluators

logger = logging.getLogger(__name__)


class AynuxEvaluators:
    """
    Collection of custom evaluators for the Aynux multi-agent system.

    Facade that delegates to specialized evaluator classes:
    - RoutingEvaluators: Intent and agent routing
    - QualityEvaluators: Response quality
    - BusinessEvaluators: Business metrics
    - LanguageEvaluators: Language detection
    """

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None

        # Initialize specialized evaluators
        self._routing = RoutingEvaluators()
        self._quality = QualityEvaluators()
        self._business = BusinessEvaluators()
        self._language = LanguageEvaluators()

        self.config = {
            "routing_accuracy_threshold": 0.8,
            "response_quality_threshold": 0.7,
            "task_completion_threshold": 0.85,
            "business_conversion_threshold": 0.15,
        }

        logger.info("Aynux evaluators initialized")

    # Routing evaluators
    def evaluate_intent_routing_accuracy(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to routing evaluators."""
        return self._routing.evaluate_intent_routing_accuracy(run, example)

    def evaluate_agent_transition_quality(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to routing evaluators."""
        return self._routing.evaluate_agent_transition_quality(run, example)

    # Quality evaluators
    def evaluate_response_quality(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to quality evaluators."""
        return self._quality.evaluate_response_quality(run, example)

    # Business evaluators
    def evaluate_task_completion_rate(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to business evaluators."""
        return self._business.evaluate_task_completion_rate(run, example)

    def evaluate_customer_satisfaction(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to business evaluators."""
        return self._business.evaluate_customer_satisfaction(run, example)

    def evaluate_conversion_potential(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to business evaluators."""
        return self._business.evaluate_conversion_potential(run, example)

    # Language evaluators
    def evaluate_language_detection_accuracy(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """Delegate to language evaluators."""
        return self._language.evaluate_language_detection_accuracy(run, example)

    def evaluate_conversation(
        self, run: Run, example: Example
    ) -> dict[str, EvaluationResult]:
        """
        Runs comprehensive evaluation across all categories for a conversation.
        """
        evaluations = {}

        evaluator_methods = [
            ("intent_routing_accuracy", self.evaluate_intent_routing_accuracy),
            ("agent_transition_quality", self.evaluate_agent_transition_quality),
            ("response_quality", self.evaluate_response_quality),
            ("task_completion_rate", self.evaluate_task_completion_rate),
            ("customer_satisfaction", self.evaluate_customer_satisfaction),
            ("conversion_potential", self.evaluate_conversion_potential),
            (
                "language_detection_accuracy",
                self.evaluate_language_detection_accuracy,
            ),
        ]

        for evaluator_name, evaluator_method in evaluator_methods:
            try:
                result = evaluator_method(run, example)
                evaluations[evaluator_name] = result
                logger.debug(
                    f"Completed evaluation: {evaluator_name} = {result.score:.2f}"
                )
            except Exception as e:
                logger.error(f"Error in evaluator {evaluator_name}: {e}")
                evaluations[evaluator_name] = EvaluationResult(
                    score=0.0,
                    explanation=f"Evaluator failed: {str(e)}",
                    category="error",
                    metadata={"error": str(e)},
                )

        return evaluations

    def get_evaluation_summary(
        self, evaluations: dict[str, EvaluationResult]
    ) -> dict[str, Any]:
        """
        Creates a summary of evaluation results with overall scores by category.
        """
        categories: dict[str, dict[str, Any]] = {}
        for eval_name, result in evaluations.items():
            category = result.category
            if category not in categories:
                categories[category] = {"scores": [], "evaluations": []}

            categories[category]["scores"].append(result.score)
            categories[category]["evaluations"].append(eval_name)

        category_summaries = {}
        for category, data in categories.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            category_summaries[category] = {
                "average_score": avg_score,
                "evaluation_count": len(data["scores"]),
                "evaluations": data["evaluations"],
            }

        all_scores = [result.score for result in evaluations.values()]
        overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return {
            "overall_score": overall_score,
            "category_summaries": category_summaries,
            "total_evaluations": len(evaluations),
            "timestamp": datetime.now().isoformat(),
        }


def create_langsmith_evaluators() -> list[LangSmithRunEvaluator]:
    """
    Creates LangSmith-compatible evaluators for automated evaluation runs.
    """
    evaluators_instance = AynuxEvaluators()
    langsmith_evaluators = []

    def routing_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_intent_routing_accuracy(run, example)
        return {
            "key": "intent_routing_accuracy",
            "score": result.score,
            "comment": result.explanation,
        }

    langsmith_evaluators.append(LangSmithRunEvaluator(routing_evaluator))

    def quality_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_response_quality(run, example)
        return {
            "key": "response_quality",
            "score": result.score,
            "comment": result.explanation,
        }

    langsmith_evaluators.append(LangSmithRunEvaluator(quality_evaluator))

    def completion_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_task_completion_rate(run, example)
        return {
            "key": "task_completion",
            "score": result.score,
            "comment": result.explanation,
        }

    langsmith_evaluators.append(LangSmithRunEvaluator(completion_evaluator))

    logger.info(f"Created {len(langsmith_evaluators)} LangSmith evaluators")
    return langsmith_evaluators


# Global singleton instance
_evaluators_instance: AynuxEvaluators | None = None


def get_evaluators_instance() -> AynuxEvaluators:
    """Get a singleton instance of AynuxEvaluators."""
    global _evaluators_instance
    if _evaluators_instance is None:
        _evaluators_instance = AynuxEvaluators()
    return _evaluators_instance


__all__ = [
    # Models
    "EvaluationResult",
    # Specialized evaluators
    "RoutingEvaluators",
    "QualityEvaluators",
    "BusinessEvaluators",
    "LanguageEvaluators",
    # Facade
    "AynuxEvaluators",
    "create_langsmith_evaluators",
    "get_evaluators_instance",
]
