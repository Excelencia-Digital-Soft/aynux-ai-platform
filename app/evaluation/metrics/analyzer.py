"""
Run Analyzer for LangSmith Metrics.

Analyzes LangSmith Run objects to extract metric values.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from langsmith.schemas import Run


@dataclass
class MetricValue:
    """A single metric measurement."""

    timestamp: datetime
    value: float
    metadata: dict[str, Any]


class RunAnalyzer:
    """
    Analyzes LangSmith Run objects to extract metrics.

    Responsibilities:
    - Extract routing accuracy from runs
    - Analyze agent selection patterns
    - Calculate response times and error rates
    - Infer customer satisfaction and conversion potential
    """

    def analyze_routing_accuracy(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze intent routing accuracy from runs."""
        values = []
        for run in runs:
            if hasattr(run, "feedback_stats") and run.feedback_stats:
                feedback = run.feedback_stats.get("routing_accuracy")
                if feedback and feedback.get("score") is not None:
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=float(feedback["score"]),
                            metadata={"run_id": run.id, "feedback": feedback},
                        )
                    )
            else:
                outputs = run.outputs or {}
                expected_agent = outputs.get("expected_agent")
                actual_agent = outputs.get("next_agent") or outputs.get("current_agent")

                if expected_agent and actual_agent:
                    accuracy = 1.0 if expected_agent == actual_agent else 0.0
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=accuracy,
                            metadata={"run_id": run.id, "inferred": True},
                        )
                    )

        return values

    def analyze_agent_selection(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze agent selection accuracy."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            agent_used = outputs.get("current_agent")

            if agent_used:
                accuracy = 0.9 if agent_used != "fallback_agent" else 0.3
                values.append(
                    MetricValue(
                        timestamp=run.end_time or run.start_time,
                        value=accuracy,
                        metadata={"run_id": run.id, "agent": agent_used},
                    )
                )

        return values

    def analyze_routing_confidence(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze routing confidence scores."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            routing_decision = outputs.get("routing_decision", {})
            confidence = routing_decision.get("confidence")

            if confidence is not None:
                values.append(
                    MetricValue(
                        timestamp=run.end_time or run.start_time,
                        value=float(confidence),
                        metadata={"run_id": run.id, "decision": routing_decision},
                    )
                )

        return values

    def analyze_response_quality(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze response quality scores."""
        values = []
        for run in runs:
            if hasattr(run, "feedback_stats") and run.feedback_stats:
                quality_feedback = run.feedback_stats.get("response_quality")
                if quality_feedback and quality_feedback.get("score") is not None:
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=float(quality_feedback["score"]),
                            metadata={"run_id": run.id, "feedback": quality_feedback},
                        )
                    )

        return values

    def analyze_task_completion(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze task completion rates."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            is_complete = outputs.get("is_complete", False)
            human_handoff = outputs.get("human_handoff_requested", False)

            if is_complete and not human_handoff:
                score = 1.0
            elif is_complete and human_handoff:
                score = 0.7
            elif human_handoff:
                score = 0.3
            else:
                score = 0.5

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=score,
                    metadata={
                        "run_id": run.id,
                        "is_complete": is_complete,
                        "human_handoff": human_handoff,
                    },
                )
            )

        return values

    def analyze_conversation_success(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze overall conversation success rates."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            is_complete = outputs.get("is_complete", False)
            has_error = run.error is not None
            agent_used = outputs.get("current_agent", "")

            success = is_complete and not has_error and agent_used not in ["fallback_agent"]

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=1.0 if success else 0.0,
                    metadata={
                        "run_id": run.id,
                        "success_factors": {
                            "complete": is_complete,
                            "no_error": not has_error,
                            "good_agent": agent_used not in ["fallback_agent"],
                        },
                    },
                )
            )

        return values

    def analyze_response_times(
        self, runs: list[Run]
    ) -> dict[str, list[MetricValue]]:
        """Analyze response time metrics."""
        response_times = []

        for run in runs:
            if run.end_time and run.start_time:
                duration_seconds = (run.end_time - run.start_time).total_seconds()
                response_times.append(
                    MetricValue(
                        timestamp=run.end_time,
                        value=duration_seconds,
                        metadata={"run_id": run.id},
                    )
                )

        if not response_times:
            return {"average": [], "p95": []}

        sorted_times = sorted([rt.value for rt in response_times])
        avg_time = sum(sorted_times) / len(sorted_times)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = (
            sorted_times[p95_index]
            if p95_index < len(sorted_times)
            else sorted_times[-1]
        )

        return {
            "average": [
                MetricValue(
                    timestamp=datetime.now(),
                    value=avg_time,
                    metadata={"sample_size": len(response_times)},
                )
            ],
            "p95": [
                MetricValue(
                    timestamp=datetime.now(),
                    value=p95_time,
                    metadata={"sample_size": len(response_times)},
                )
            ],
        }

    def analyze_error_rates(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze error rates."""
        total_runs = len(runs)
        error_runs = len([run for run in runs if run.error is not None])
        error_rate = error_runs / total_runs if total_runs > 0 else 0.0

        return [
            MetricValue(
                timestamp=datetime.now(),
                value=error_rate,
                metadata={"total_runs": total_runs, "error_runs": error_runs},
            )
        ]

    def analyze_customer_satisfaction(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze inferred customer satisfaction."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            processing_time = (
                (run.end_time - run.start_time).total_seconds()
                if run.end_time and run.start_time
                else 5.0
            )
            is_complete = outputs.get("is_complete", False)
            agent_transitions = len(outputs.get("agent_history", []))

            time_score = (
                1.0
                if processing_time < 3.0
                else (0.5 if processing_time < 6.0 else 0.2)
            )
            completion_score = 1.0 if is_complete else 0.3
            routing_score = (
                1.0
                if agent_transitions <= 1
                else (0.7 if agent_transitions <= 2 else 0.4)
            )

            satisfaction = (time_score + completion_score + routing_score) / 3

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=satisfaction,
                    metadata={
                        "run_id": run.id,
                        "factors": {
                            "response_time": processing_time,
                            "completed": is_complete,
                            "transitions": agent_transitions,
                        },
                    },
                )
            )

        return values

    def analyze_conversion_potential(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze conversion potential scores."""
        values = []
        for run in runs:
            inputs = run.inputs or {}
            outputs = run.outputs or {}

            user_message = inputs.get("message", "").lower()
            agent_used = outputs.get("current_agent", "")

            buying_keywords = [
                "comprar",
                "precio",
                "costo",
                "cuanto",
                "oferta",
                "descuento",
            ]
            buying_signals = sum(
                1 for keyword in buying_keywords if keyword in user_message
            )

            if (
                agent_used in ["product_agent", "smart_product_agent"]
                and buying_signals > 0
            ):
                potential = min(1.0, 0.4 + (buying_signals * 0.2))
            elif agent_used == "promotions_agent":
                potential = 0.6
            else:
                potential = 0.1

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=potential,
                    metadata={
                        "run_id": run.id,
                        "agent_used": agent_used,
                        "buying_signals": buying_signals,
                    },
                )
            )

        return values

    def analyze_escalation_rates(self, runs: list[Run]) -> list[MetricValue]:
        """Analyze human escalation rates."""
        total_conversations = len(runs)
        escalated_conversations = len(
            [
                run
                for run in runs
                if (run.outputs or {}).get("human_handoff_requested", False)
            ]
        )

        escalation_rate = (
            escalated_conversations / total_conversations
            if total_conversations > 0
            else 0.0
        )

        return [
            MetricValue(
                timestamp=datetime.now(),
                value=escalation_rate,
                metadata={
                    "total_conversations": total_conversations,
                    "escalated_conversations": escalated_conversations,
                },
            )
        ]
