"""
Custom evaluators for LangSmith integration in Aynux.

This module provides comprehensive evaluation capabilities for the multi-agent system:
- Agent routing accuracy
- Response quality and relevance
- Task completion rate
- Business metrics (conversion, satisfaction)
- Language detection accuracy
"""

import logging
import re
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional

from langsmith.schemas import Example, Run

try:
    from langsmith.evaluation import LangSmithRunEvaluator
except ImportError:
    # Fallback class if not available
    class LangSmithRunEvaluator:
        def __init__(self, evaluator_func):
            self.evaluator_func = evaluator_func


from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer

logger = logging.getLogger(__name__)


class EvaluationResult(BaseModel):
    """Standard evaluation result structure."""

    score: float = Field(..., description="Evaluation score (0.0 to 1.0)", ge=0.0, le=1.0)
    explanation: str = Field(..., description="Human-readable explanation of the score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional evaluation metadata")
    category: str = Field(..., description="Evaluation category (quality, accuracy, business, etc.)")


class AynuxEvaluators:
    """Collection of custom evaluators for the Aynux multi-agent system."""

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None

        # Evaluation thresholds and configurations
        self.config = {
            "routing_accuracy_threshold": 0.8,
            "response_quality_threshold": 0.7,
            "task_completion_threshold": 0.85,
            "business_conversion_threshold": 0.15,
        }

        logger.info("Aynux evaluators initialized")

    def _create_evaluator_decorator(self, evaluator_name: str, category: str):
        """Creates a decorator that wraps evaluators with error handling and logging."""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs) -> EvaluationResult:
                start_time = datetime.now()

                try:
                    # Call the function normally (not async)
                    result = func(*args, **kwargs)

                    # Ensure result is an EvaluationResult
                    if not isinstance(result, EvaluationResult):
                        result = EvaluationResult(
                            score=result.get("score", 0.0),
                            explanation=result.get("explanation", "No explanation provided"),
                            category=category,
                            metadata=result.get("metadata", {}),
                        )

                    duration = (datetime.now() - start_time).total_seconds()
                    logger.debug(
                        f"Evaluator {evaluator_name} completed in {duration:.2f}s with score {result.score:.2f}"
                    )

                    return result

                except Exception as e:
                    logger.error(f"Error in evaluator {evaluator_name}: {e}")
                    return EvaluationResult(
                        score=0.0,
                        explanation=f"Evaluator failed with error: {str(e)}",
                        category=category,
                        metadata={"error": str(e), "evaluator": evaluator_name},
                    )

            return wrapper

        return decorator

    # ============================================================================
    # INTENT ROUTING AND AGENT SELECTION EVALUATORS
    # ============================================================================

    def evaluate_intent_routing_accuracy(self, run: Run, example: Example) -> EvaluationResult:
        """
        Evaluates accuracy of intent detection and agent routing decisions.

        This evaluator checks if the supervisor correctly identified the user's intent
        and routed to the appropriate specialized agent.
        """
        # Extract routing information from run metadata
        routing_decision = run.outputs.get("routing_decision", {})
        expected_agent = example.outputs.get("expected_agent")
        actual_agent = run.outputs.get("next_agent") or run.outputs.get("current_agent")

        if not expected_agent or not actual_agent:
            return EvaluationResult(
                score=0.0,
                explanation="Missing expected or actual agent information",
                category="routing",
                metadata={"expected": expected_agent, "actual": actual_agent},
            )

        # Calculate accuracy score
        correct_routing = expected_agent == actual_agent
        base_score = 1.0 if correct_routing else 0.0

        # Consider confidence level if available
        confidence = routing_decision.get("confidence", 0.5)
        confidence_penalty = max(0, 0.8 - confidence) * 0.2  # Penalty for low confidence

        final_score = max(0.0, base_score - confidence_penalty)

        explanation = (
            f"Routing {'correct' if correct_routing else 'incorrect'}: "
            f"expected {expected_agent}, got {actual_agent}. "
            f"Confidence: {confidence:.2f}"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="routing",
            metadata={
                "expected_agent": expected_agent,
                "actual_agent": actual_agent,
                "confidence": confidence,
                "routing_decision": routing_decision,
            },
        )

    def evaluate_agent_transition_quality(self, run: Run, _: Example) -> EvaluationResult:
        """
        Evaluates the quality of agent transitions and re-routing decisions.

        Checks for appropriate escalation to support, fallback handling, and
        conversation flow management.
        """
        agent_history = run.outputs.get("agent_history", [])
        transitions = len(agent_history) - 1 if len(agent_history) > 1 else 0

        # Calculate transition quality score
        if transitions == 0:
            # Single agent handled the request - ideal scenario
            score = 1.0
            explanation = "Request handled by single agent - optimal routing"
        elif transitions <= 2:
            # Reasonable number of transitions
            score = 0.8
            explanation = f"Handled with {transitions} agent transitions - acceptable routing"
        else:
            # Too many transitions indicate routing problems
            score = max(0.2, 1.0 - (transitions * 0.15))
            explanation = f"Excessive agent transitions ({transitions}) - routing issues detected"

        return EvaluationResult(
            score=score,
            explanation=explanation,
            category="routing",
            metadata={"agent_history": agent_history, "transition_count": transitions},
        )

    # ============================================================================
    # RESPONSE QUALITY AND RELEVANCE EVALUATORS
    # ============================================================================

    def evaluate_response_quality(self, run: Run, _: Example) -> EvaluationResult:
        """
        Evaluates overall response quality including relevance, completeness, and helpfulness.

        Considers factors like:
        - Response relevance to user query
        - Completeness of information provided
        - Language quality and clarity
        - Professional tone and helpfulness
        """
        user_message = run.inputs.get("message", "")
        assistant_response = ""

        # Extract assistant response from messages
        messages = run.outputs.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                assistant_response = msg.get("content", "")
                break
            elif hasattr(msg, "content"):
                assistant_response = getattr(msg, "content", "")
                break

        if not assistant_response:
            return EvaluationResult(score=0.0, explanation="No assistant response found", category="quality")

        # Quality assessment criteria
        score_components = {}

        # 1. Response length and substance (20%)
        response_length = len(assistant_response.strip())
        if response_length < 20:
            score_components["length"] = 0.2
        elif response_length < 100:
            score_components["length"] = 0.6
        else:
            score_components["length"] = 1.0

        # 2. Relevance keywords (30%)
        user_keywords = self._extract_keywords(user_message.lower())
        response_keywords = self._extract_keywords(assistant_response.lower())

        if user_keywords:
            keyword_overlap = len(user_keywords.intersection(response_keywords)) / len(user_keywords)
            score_components["relevance"] = min(1.0, keyword_overlap * 1.5)
        else:
            score_components["relevance"] = 0.7  # Neutral score if no clear keywords

        # 3. Professional language indicators (20%)
        professional_indicators = ["gracias", "por favor", "disculp", "ayud", "puede", "servicio"]
        professional_score = sum(
            1 for indicator in professional_indicators if indicator in assistant_response.lower()
        ) / len(professional_indicators)
        score_components["professionalism"] = min(1.0, professional_score * 2)

        # 4. No negative indicators (30%)
        negative_indicators = ["error", "no pued", "no s\u00e9", "disculp", "problem", "fall\u00f3"]
        negative_count = sum(1 for indicator in negative_indicators if indicator in assistant_response.lower())
        score_components["negative_indicators"] = max(0.0, 1.0 - (negative_count * 0.2))

        # Calculate weighted final score
        weights = {"length": 0.2, "relevance": 0.3, "professionalism": 0.2, "negative_indicators": 0.3}
        final_score = sum(score_components[component] * weights[component] for component in score_components)

        explanation = (
            f"Quality score breakdown: "
            f"Length: {score_components['length']:.2f}, "
            f"Relevance: {score_components['relevance']:.2f}, "
            f"Professional: {score_components['professionalism']:.2f}, "
            f"Clean: {score_components['negative_indicators']:.2f}"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="quality",
            metadata={
                "response_length": response_length,
                "score_components": score_components,
                "user_keywords": list(user_keywords),
                "response_keywords": list(response_keywords),
            },
        )

    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text for relevance analysis."""
        # Remove common Spanish stop words and extract meaningful terms
        stop_words = {
            "el",
            "la",
            "de",
            "que",
            "y",
            "a",
            "en",
            "un",
            "es",
            "se",
            "no",
            "te",
            "lo",
            "le",
            "da",
            "su",
            "por",
            "son",
            "con",
            "para",
            "al",
            "del",
            "los",
            "las",
            "una",
            "sobre",
        }

        # Extract words (minimum 3 characters, excluding stop words)
        words = re.findall(r"\b[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}\b", text.lower())
        return {word for word in words if word not in stop_words}

    # ============================================================================
    # TASK COMPLETION AND SUCCESS EVALUATORS
    # ============================================================================

    def evaluate_task_completion_rate(self, run: Run, _: Example) -> EvaluationResult:
        """
        Evaluates whether the conversation successfully completed the user's task.

        Looks for indicators of successful task completion:
        - Product information provided for product queries
        - Support issues resolved
        - Questions answered satisfactorily
        """
        is_complete = run.outputs.get("is_complete", False)
        human_handoff = run.outputs.get("human_handoff_requested", False)
        agent_used = run.outputs.get("current_agent", "")

        # Base completion score
        if is_complete and not human_handoff:
            base_score = 1.0
        elif is_complete and human_handoff:
            base_score = 0.7  # Completed but needed human assistance
        elif human_handoff:
            base_score = 0.3  # Escalated to human - partial success
        else:
            base_score = 0.5  # Conversation ongoing

        # Adjust score based on agent type and expected outcomes
        agent_performance_multipliers = {
            "product_agent": 1.0,  # Expected to provide product info
            "category_agent": 1.0,  # Expected to provide category info
            "support_agent": 0.9,  # May need escalation
            "fallback_agent": 0.6,  # Indicates routing issues
            "farewell_agent": 1.0,  # Successful conversation closure
        }

        multiplier = agent_performance_multipliers.get(agent_used, 0.8)
        final_score = base_score * multiplier

        explanation = (
            f"Task completion: {'Yes' if is_complete else 'No'}, "
            f"Human handoff: {'Yes' if human_handoff else 'No'}, "
            f"Agent: {agent_used}, Score: {final_score:.2f}"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="completion",
            metadata={
                "is_complete": is_complete,
                "human_handoff_requested": human_handoff,
                "agent_used": agent_used,
                "base_score": base_score,
                "multiplier": multiplier,
            },
        )

    # ============================================================================
    # BUSINESS METRICS EVALUATORS
    # ============================================================================

    def evaluate_customer_satisfaction(self, run: Run, _: Example) -> EvaluationResult:
        """
        Infers customer satisfaction from conversation patterns and outcomes.

        Uses indicators like:
        - Response time
        - Number of agent transfers
        - Task completion
        - Language sentiment
        """
        # Get conversation metrics
        processing_time = run.outputs.get("processing_time_ms", 0) / 1000.0  # Convert to seconds
        agent_transitions = len(run.outputs.get("agent_history", []))
        is_complete = run.outputs.get("is_complete", False)

        # Extract last user message to check for satisfaction indicators
        messages = run.outputs.get("messages", [])
        user_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "user"]
        last_user_message = user_messages[-1].get("content", "") if user_messages else ""

        # Satisfaction scoring components
        score_components = {}

        # 1. Response time satisfaction (25%)
        if processing_time < 2.0:
            score_components["response_time"] = 1.0
        elif processing_time < 5.0:
            score_components["response_time"] = 0.8
        else:
            score_components["response_time"] = 0.5

        # 2. Routing efficiency (25%)
        if agent_transitions <= 1:
            score_components["routing"] = 1.0
        elif agent_transitions <= 2:
            score_components["routing"] = 0.7
        else:
            score_components["routing"] = 0.4

        # 3. Task completion (30%)
        score_components["completion"] = 1.0 if is_complete else 0.3

        # 4. Language sentiment indicators (20%)
        positive_indicators = ["gracias", "perfect", "bien", "excelente", "bueno"]
        negative_indicators = ["mal", "p\u00e9sim", "horrible", "no sirv", "odio"]

        positive_count = sum(1 for indicator in positive_indicators if indicator in last_user_message.lower())
        negative_count = sum(1 for indicator in negative_indicators if indicator in last_user_message.lower())

        if positive_count > negative_count:
            score_components["sentiment"] = 0.9
        elif negative_count > positive_count:
            score_components["sentiment"] = 0.2
        else:
            score_components["sentiment"] = 0.6  # Neutral

        # Calculate weighted score
        weights = {"response_time": 0.25, "routing": 0.25, "completion": 0.30, "sentiment": 0.20}
        final_score = sum(score_components[component] * weights[component] for component in score_components)

        explanation = (
            f"Satisfaction indicators: "
            f"Response time: {processing_time:.1f}s ({score_components['response_time']:.2f}), "
            f"Routing: {agent_transitions} transfers ({score_components['routing']:.2f}), "
            f"Completion: {'Yes' if is_complete else 'No'} ({score_components['completion']:.2f})"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="business",
            metadata={
                "processing_time_seconds": processing_time,
                "agent_transitions": agent_transitions,
                "is_complete": is_complete,
                "score_components": score_components,
            },
        )

    def evaluate_conversion_potential(self, run: Run, _: Example) -> EvaluationResult:
        """
        Evaluates the potential for conversation to lead to a sale or conversion.

        Looks for buying signals, product interest, and engagement indicators.
        """
        user_message = run.inputs.get("message", "").lower()
        assistant_response = ""

        # Extract assistant response
        messages = run.outputs.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                assistant_response = msg.get("content", "")
                break

        # Conversion signal analysis
        score_components = {}

        # 1. Buying intent keywords in user message (40%)
        buying_keywords = [
            "comprar",
            "precio",
            "costo",
            "cuanto",
            "oferta",
            "descuento",
            "disponible",
            "stock",
            "envio",
            "pago",
            "tarjeta",
        ]
        buying_signals = sum(1 for keyword in buying_keywords if keyword in user_message)
        score_components["buying_intent"] = min(1.0, buying_signals * 0.3)

        # 2. Product information provided (30%)
        agent_used = run.outputs.get("current_agent", "")
        if agent_used in ["product_agent", "smart_product_agent"]:
            # Check if product details were provided
            product_indicators = ["precio", "$", "stock", "disponible", "caracteristica"]
            product_info_score = sum(1 for indicator in product_indicators if indicator in assistant_response.lower())
            score_components["product_info"] = min(1.0, product_info_score * 0.25)
        else:
            score_components["product_info"] = 0.0

        # 3. Engagement level (20%)
        conversation_length = len(user_message) + len(assistant_response)
        if conversation_length > 200:
            score_components["engagement"] = 1.0
        elif conversation_length > 100:
            score_components["engagement"] = 0.7
        else:
            score_components["engagement"] = 0.3

        # 4. No barriers or negative indicators (10%)
        barriers = ["no disponible", "sin stock", "agotado", "no tenemos"]
        barrier_count = sum(1 for barrier in barriers if barrier in assistant_response.lower())
        score_components["no_barriers"] = max(0.0, 1.0 - (barrier_count * 0.5))

        # Calculate weighted score
        weights = {"buying_intent": 0.4, "product_info": 0.3, "engagement": 0.2, "no_barriers": 0.1}
        final_score = sum(score_components[component] * weights[component] for component in score_components)

        explanation = (
            f"Conversion potential: "
            f"Buying signals: {score_components['buying_intent']:.2f}, "
            f"Product info: {score_components['product_info']:.2f}, "
            f"Engagement: {score_components['engagement']:.2f}"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="business",
            metadata={
                "agent_used": agent_used,
                "conversation_length": conversation_length,
                "score_components": score_components,
                "buying_signals": buying_signals,
            },
        )

    # ============================================================================
    # LANGUAGE AND LOCALIZATION EVALUATORS
    # ============================================================================

    def evaluate_language_detection_accuracy(self, run: Run, _: Example) -> EvaluationResult:
        """
        Evaluates accuracy of language detection and appropriate response language.

        Ensures the system correctly identifies Spanish input and responds in Spanish.
        """
        user_message = run.inputs.get("message", "")
        assistant_response = ""

        # Extract assistant response
        messages = run.outputs.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                assistant_response = msg.get("content", "")
                break

        # Language detection scoring
        score_components = {}

        # 1. Spanish input detection (50%)
        spanish_indicators = [
            "que",
            "como",
            "donde",
            "cuando",
            "por",
            "para",
            "con",
            "sin",
            "mas",
            "menos",
            "muy",
            "bien",
            "mal",
            "si",
            "no",
            "gracias",
        ]
        spanish_count = sum(1 for indicator in spanish_indicators if indicator in user_message.lower())

        if spanish_count >= 2:
            is_spanish_input = True
            score_components["input_detection"] = 1.0
        elif spanish_count == 1:
            is_spanish_input = True
            score_components["input_detection"] = 0.7
        else:
            is_spanish_input = False
            score_components["input_detection"] = 0.3

        # 2. Spanish response generation (50%)
        if is_spanish_input:
            spanish_response_indicators = spanish_indicators + ["hola", "buenas", "ayudar", "servicio"]
            response_spanish_count = sum(
                1 for indicator in spanish_response_indicators if indicator in assistant_response.lower()
            )

            if response_spanish_count >= 2:
                score_components["response_language"] = 1.0
            elif response_spanish_count == 1:
                score_components["response_language"] = 0.6
            else:
                score_components["response_language"] = 0.2
        else:
            # For non-Spanish input, neutral score
            response_spanish_count = 0  # Initialize for non-Spanish input
            score_components["response_language"] = 0.7

        # Calculate final score
        final_score = (score_components["input_detection"] + score_components["response_language"]) / 2

        explanation = (
            f"Language handling: "
            f"Spanish input detected: {is_spanish_input}, "
            f"Appropriate response: {score_components['response_language']:.2f}"
        )

        return EvaluationResult(
            score=final_score,
            explanation=explanation,
            category="language",
            metadata={
                "spanish_input_detected": is_spanish_input,
                "spanish_indicators_count": spanish_count,
                "response_spanish_count": response_spanish_count,
                "score_components": score_components,
            },
        )

    # ============================================================================
    # COMPREHENSIVE EVALUATION ORCHESTRATOR
    # ============================================================================

    def evaluate_conversation(self, run: Run, example: Example) -> Dict[str, EvaluationResult]:
        """
        Runs comprehensive evaluation across all categories for a conversation.

        Returns:
            Dictionary mapping evaluator names to their results
        """
        evaluations = {}

        # Run all evaluators
        evaluator_methods = [
            ("intent_routing_accuracy", self.evaluate_intent_routing_accuracy),
            ("agent_transition_quality", self.evaluate_agent_transition_quality),
            ("response_quality", self.evaluate_response_quality),
            ("task_completion_rate", self.evaluate_task_completion_rate),
            ("customer_satisfaction", self.evaluate_customer_satisfaction),
            ("conversion_potential", self.evaluate_conversion_potential),
            ("language_detection_accuracy", self.evaluate_language_detection_accuracy),
        ]

        for evaluator_name, evaluator_method in evaluator_methods:
            try:
                result = evaluator_method(run, example)
                evaluations[evaluator_name] = result
                logger.debug(f"Completed evaluation: {evaluator_name} = {result.score:.2f}")
            except Exception as e:
                logger.error(f"Error in evaluator {evaluator_name}: {e}")
                evaluations[evaluator_name] = EvaluationResult(
                    score=0.0, explanation=f"Evaluator failed: {str(e)}", category="error", metadata={"error": str(e)}
                )

        return evaluations

    def get_evaluation_summary(self, evaluations: Dict[str, EvaluationResult]) -> Dict[str, Any]:
        """
        Creates a summary of evaluation results with overall scores by category.
        """
        categories = {}
        for eval_name, result in evaluations.items():
            category = result.category
            if category not in categories:
                categories[category] = {"scores": [], "evaluations": []}

            categories[category]["scores"].append(result.score)
            categories[category]["evaluations"].append(eval_name)

        # Calculate category averages
        category_summaries = {}
        for category, data in categories.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            category_summaries[category] = {
                "average_score": avg_score,
                "evaluation_count": len(data["scores"]),
                "evaluations": data["evaluations"],
            }

        # Overall system score
        all_scores = [result.score for result in evaluations.values()]
        overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return {
            "overall_score": overall_score,
            "category_summaries": category_summaries,
            "total_evaluations": len(evaluations),
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================================
# LANGSMITH EVALUATOR INTEGRATION
# ============================================================================


def create_langsmith_evaluators() -> List[LangSmithRunEvaluator]:
    """
    Creates LangSmith-compatible evaluators for automated evaluation runs.

    Returns:
        List of evaluators that can be used with LangSmith's evaluation framework
    """
    evaluators_instance = AynuxEvaluators()

    # Wrap evaluators for LangSmith compatibility
    langsmith_evaluators = []

    # Intent routing evaluator
    def routing_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_intent_routing_accuracy(run, example)
        return {"key": "intent_routing_accuracy", "score": result.score, "comment": result.explanation}

    langsmith_evaluators.append(LangSmithRunEvaluator(routing_evaluator))

    # Response quality evaluator
    def quality_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_response_quality(run, example)
        return {"key": "response_quality", "score": result.score, "comment": result.explanation}

    langsmith_evaluators.append(LangSmithRunEvaluator(quality_evaluator))

    # Task completion evaluator
    def completion_evaluator(run: Run, example: Example) -> dict:
        result = evaluators_instance.evaluate_task_completion_rate(run, example)
        return {"key": "task_completion", "score": result.score, "comment": result.explanation}

    langsmith_evaluators.append(LangSmithRunEvaluator(completion_evaluator))

    logger.info(f"Created {len(langsmith_evaluators)} LangSmith evaluators")
    return langsmith_evaluators


# Global singleton instance
_evaluators_instance: Optional[AynuxEvaluators] = None


def get_evaluators_instance() -> AynuxEvaluators:
    """Get a singleton instance of AynuxEvaluators."""
    global _evaluators_instance
    if _evaluators_instance is None:
        _evaluators_instance = AynuxEvaluators()
    return _evaluators_instance

