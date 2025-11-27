"""
Quality Evaluators.

Evaluators for response quality, relevance, and professionalism.
"""

import re

from langsmith.schemas import Example, Run

from app.evaluation.evaluators.models import EvaluationResult


class QualityEvaluators:
    """
    Evaluators for response quality assessment.

    Responsibilities:
    - Evaluate response relevance
    - Assess professional language
    - Check for negative indicators
    """

    def evaluate_response_quality(
        self, run: Run, _: Example
    ) -> EvaluationResult:
        """
        Evaluates overall response quality including relevance, completeness,
        and helpfulness.
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
            elif hasattr(msg, "content"):
                assistant_response = getattr(msg, "content", "")
                break

        if not assistant_response:
            return EvaluationResult(
                score=0.0,
                explanation="No assistant response found",
                category="quality",
            )

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
            keyword_overlap = len(
                user_keywords.intersection(response_keywords)
            ) / len(user_keywords)
            score_components["relevance"] = min(1.0, keyword_overlap * 1.5)
        else:
            score_components["relevance"] = 0.7

        # 3. Professional language indicators (20%)
        professional_indicators = [
            "gracias",
            "por favor",
            "disculp",
            "ayud",
            "puede",
            "servicio",
        ]
        professional_score = sum(
            1
            for indicator in professional_indicators
            if indicator in assistant_response.lower()
        ) / len(professional_indicators)
        score_components["professionalism"] = min(1.0, professional_score * 2)

        # 4. No negative indicators (30%)
        negative_indicators = [
            "error",
            "no pued",
            "no sé",
            "disculp",
            "problem",
            "falló",
        ]
        negative_count = sum(
            1
            for indicator in negative_indicators
            if indicator in assistant_response.lower()
        )
        score_components["negative_indicators"] = max(
            0.0, 1.0 - (negative_count * 0.2)
        )

        weights = {
            "length": 0.2,
            "relevance": 0.3,
            "professionalism": 0.2,
            "negative_indicators": 0.3,
        }
        final_score = sum(
            score_components[component] * weights[component]
            for component in score_components
        )

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

        words = re.findall(r"\b[a-záéíóúñ]{3,}\b", text.lower())
        return {word for word in words if word not in stop_words}
