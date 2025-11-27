"""
Language Evaluators.

Evaluators for language detection and localization accuracy.
"""

from langsmith.schemas import Example, Run

from app.evaluation.evaluators.models import EvaluationResult


class LanguageEvaluators:
    """
    Evaluators for language detection and response language accuracy.

    Responsibilities:
    - Detect input language (Spanish focus)
    - Verify response language matches input
    - Assess localization quality
    """

    def evaluate_language_detection_accuracy(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Evaluates accuracy of language detection and appropriate response language.
        """
        run_inputs = run.inputs or {}
        run_outputs = run.outputs or {}
        user_message = run_inputs.get("message", "")
        assistant_response = ""

        messages = run_outputs.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                assistant_response = msg.get("content", "")
                break

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
        spanish_count = sum(
            1
            for indicator in spanish_indicators
            if indicator in user_message.lower()
        )

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
            spanish_response_indicators = spanish_indicators + [
                "hola",
                "buenas",
                "ayudar",
                "servicio",
            ]
            response_spanish_count = sum(
                1
                for indicator in spanish_response_indicators
                if indicator in assistant_response.lower()
            )

            if response_spanish_count >= 2:
                score_components["response_language"] = 1.0
            elif response_spanish_count == 1:
                score_components["response_language"] = 0.6
            else:
                score_components["response_language"] = 0.2
        else:
            response_spanish_count = 0
            score_components["response_language"] = 0.7

        final_score = (
            score_components["input_detection"]
            + score_components["response_language"]
        ) / 2

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
