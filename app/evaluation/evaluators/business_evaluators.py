"""
Business Evaluators.

Evaluators for business metrics: satisfaction, conversion, and task completion.
"""

from langsmith.schemas import Example, Run

from app.evaluation.evaluators.models import EvaluationResult


class BusinessEvaluators:
    """
    Evaluators for business metrics assessment.

    Responsibilities:
    - Evaluate customer satisfaction
    - Assess conversion potential
    - Measure task completion rate
    """

    def evaluate_task_completion_rate(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Evaluates whether the conversation successfully completed the user's task.
        """
        run_outputs = run.outputs or {}
        is_complete = run_outputs.get("is_complete", False)
        human_handoff = run_outputs.get("human_handoff_requested", False)
        agent_used = run_outputs.get("current_agent", "")

        if is_complete and not human_handoff:
            base_score = 1.0
        elif is_complete and human_handoff:
            base_score = 0.7
        elif human_handoff:
            base_score = 0.3
        else:
            base_score = 0.5

        agent_performance_multipliers = {
            "product_agent": 1.0,
            "category_agent": 1.0,
            "support_agent": 0.9,
            "fallback_agent": 0.6,
            "farewell_agent": 1.0,
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

    def evaluate_customer_satisfaction(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Infers customer satisfaction from conversation patterns and outcomes.
        """
        run_outputs = run.outputs or {}
        processing_time = run_outputs.get("processing_time_ms", 0) / 1000.0
        agent_transitions = len(run_outputs.get("agent_history", []))
        is_complete = run_outputs.get("is_complete", False)

        messages = run_outputs.get("messages", [])
        user_messages = [
            msg
            for msg in messages
            if isinstance(msg, dict) and msg.get("role") == "user"
        ]
        last_user_message = (
            user_messages[-1].get("content", "") if user_messages else ""
        )

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
        negative_indicators = ["mal", "pésim", "horrible", "no sirv", "odio"]

        positive_count = sum(
            1
            for indicator in positive_indicators
            if indicator in last_user_message.lower()
        )
        negative_count = sum(
            1
            for indicator in negative_indicators
            if indicator in last_user_message.lower()
        )

        if positive_count > negative_count:
            score_components["sentiment"] = 0.9
        elif negative_count > positive_count:
            score_components["sentiment"] = 0.2
        else:
            score_components["sentiment"] = 0.6

        weights = {
            "response_time": 0.25,
            "routing": 0.25,
            "completion": 0.30,
            "sentiment": 0.20,
        }
        final_score = sum(
            score_components[component] * weights[component]
            for component in score_components
        )

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

    def evaluate_conversion_potential(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Evaluates the potential for conversation to lead to a sale or conversion.
        """
        run_inputs = run.inputs or {}
        run_outputs = run.outputs or {}
        user_message = run_inputs.get("message", "").lower()
        assistant_response = ""

        messages = run_outputs.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                assistant_response = msg.get("content", "")
                break

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
        buying_signals = sum(
            1 for keyword in buying_keywords if keyword in user_message
        )
        score_components["buying_intent"] = min(1.0, buying_signals * 0.3)

        # 2. Product information provided (30%)
        agent_used = run_outputs.get("current_agent", "")
        if agent_used in ["product_agent", "smart_product_agent"]:
            product_indicators = [
                "precio",
                "$",
                "stock",
                "disponible",
                "caracteristica",
            ]
            product_info_score = sum(
                1
                for indicator in product_indicators
                if indicator in assistant_response.lower()
            )
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
        barrier_count = sum(
            1 for barrier in barriers if barrier in assistant_response.lower()
        )
        score_components["no_barriers"] = max(0.0, 1.0 - (barrier_count * 0.5))

        weights = {
            "buying_intent": 0.4,
            "product_info": 0.3,
            "engagement": 0.2,
            "no_barriers": 0.1,
        }
        final_score = sum(
            score_components[component] * weights[component]
            for component in score_components
        )

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
