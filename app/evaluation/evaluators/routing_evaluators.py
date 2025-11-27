"""
Routing Evaluators.

Evaluators for intent routing and agent selection accuracy.
"""

from langsmith.schemas import Example, Run

from app.evaluation.evaluators.models import EvaluationResult


class RoutingEvaluators:
    """
    Evaluators for intent routing and agent selection.

    Responsibilities:
    - Evaluate intent detection accuracy
    - Assess agent routing decisions
    - Measure transition quality
    """

    def evaluate_intent_routing_accuracy(
        self, run: Run, example: Example
    ) -> EvaluationResult:
        """
        Evaluates accuracy of intent detection and agent routing decisions.
        """
        run_outputs = run.outputs or {}
        example_outputs = example.outputs or {}
        routing_decision = run_outputs.get("routing_decision", {})
        expected_agent = example_outputs.get("expected_agent")
        actual_agent = run_outputs.get("next_agent") or run_outputs.get(
            "current_agent"
        )

        if not expected_agent or not actual_agent:
            return EvaluationResult(
                score=0.0,
                explanation="Missing expected or actual agent information",
                category="routing",
                metadata={"expected": expected_agent, "actual": actual_agent},
            )

        correct_routing = expected_agent == actual_agent
        base_score = 1.0 if correct_routing else 0.0

        confidence = routing_decision.get("confidence", 0.5)
        confidence_penalty = max(0, 0.8 - confidence) * 0.2

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

    def evaluate_agent_transition_quality(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Evaluates the quality of agent transitions and re-routing decisions.
        """
        run_outputs = run.outputs or {}
        agent_history = run_outputs.get("agent_history", [])
        transitions = len(agent_history) - 1 if len(agent_history) > 1 else 0

        if transitions == 0:
            score = 1.0
            explanation = "Request handled by single agent - optimal routing"
        elif transitions <= 2:
            score = 0.8
            explanation = (
                f"Handled with {transitions} agent transitions - acceptable routing"
            )
        else:
            score = max(0.2, 1.0 - (transitions * 0.15))
            explanation = (
                f"Excessive agent transitions ({transitions}) - routing issues detected"
            )

        return EvaluationResult(
            score=score,
            explanation=explanation,
            category="routing",
            metadata={
                "agent_history": agent_history,
                "transition_count": transitions,
            },
        )
