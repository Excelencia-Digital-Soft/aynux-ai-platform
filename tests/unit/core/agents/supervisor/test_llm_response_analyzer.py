"""
Unit tests for LLMResponseAnalyzer.

Tests cover:
1. Guards and early returns (disabled, no ollama, high heuristic)
2. JSON parsing (valid, malformed, with think tags)
3. Enum mapping (quality, action, hallucination risk)
4. Hallucination detection (by type, with RAG context, Excelencia-specific)
5. Error handling (timeout, exceptions)
6. Text parsing fallback
7. Conversation summary building
8. Integration with SupervisorAgent

Run with: uv run pytest tests/unit/core/agents/supervisor/test_llm_response_analyzer.py -v
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.graph.agents.supervisor.llm_response_analyzer import LLMResponseAnalyzer
from app.core.graph.agents.supervisor.schemas.analyzer_schemas import (
    AnalyzerFallbackResult,
    HallucinationRisk,
    LLMResponseAnalysis,
    RecommendedAction,
    ResponseQuality,
)


# ============================================================================
# TEST CLASS: Guards and Early Returns
# ============================================================================


class TestLLMResponseAnalyzerGuards:
    """Tests for early returns and guard conditions."""

    @pytest.mark.asyncio
    async def test_analyzer_disabled_returns_fallback(
        self, mock_ollama_with_llm, analyzer_config_disabled
    ):
        """When analyzer is disabled, should return AnalyzerFallbackResult."""
        mock_ollama, _ = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_disabled)

        result = await analyzer.analyze(
            user_message="Test question",
            agent_response="Test response",
            agent_name="test_agent",
            conversation_context={"messages": []},
            heuristic_score=0.7,
        )

        assert isinstance(result, AnalyzerFallbackResult)
        assert result.used_fallback is True
        assert "disabled" in result.reason.lower()
        assert result.heuristic_score == 0.7

    @pytest.mark.asyncio
    async def test_no_ollama_instance_returns_fallback(self, analyzer_config_enabled):
        """When ollama is None, should return AnalyzerFallbackResult."""
        analyzer = LLMResponseAnalyzer(ollama=None, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test question",
            agent_response="Test response",
            agent_name="test_agent",
            conversation_context={"messages": []},
            heuristic_score=0.5,
        )

        assert isinstance(result, AnalyzerFallbackResult)
        assert result.used_fallback is True
        assert "no llm instance" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_skip_llm_high_heuristic_score(
        self, mock_ollama_with_llm, analyzer_config_enabled
    ):
        """When heuristic score >= 0.90 (default threshold), should skip LLM."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test question",
            agent_response="Test response",
            agent_name="test_agent",
            conversation_context={"messages": []},
            heuristic_score=0.92,  # Above 0.90 threshold
        )

        # Should NOT call LLM
        mock_llm.ainvoke.assert_not_called()

        # Should return LLMResponseAnalysis with excellent quality
        assert isinstance(result, LLMResponseAnalysis)
        assert result.quality == ResponseQuality.EXCELLENT
        assert result.overall_score == 0.92
        assert result.recommended_action == RecommendedAction.ACCEPT
        assert "skipped" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_skip_llm_exact_threshold(
        self, mock_ollama_with_llm, analyzer_config_enabled
    ):
        """When heuristic score == 0.90 (threshold), should skip LLM."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context={"messages": []},
            heuristic_score=0.90,
        )

        mock_llm.ainvoke.assert_not_called()
        assert isinstance(result, LLMResponseAnalysis)
        assert result.quality == ResponseQuality.EXCELLENT

    @pytest.mark.asyncio
    async def test_calls_llm_below_threshold(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_good,
        sample_conversation_context_with_rag,
    ):
        """When heuristic score < 0.90 (threshold), should call LLM."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_good)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test question",
            agent_response="Test response",
            agent_name="test_agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.7,
        )

        mock_llm.ainvoke.assert_called_once()
        assert isinstance(result, LLMResponseAnalysis)

    @pytest.mark.asyncio
    async def test_custom_skip_threshold(
        self, mock_ollama_with_llm, analyzer_config_custom_threshold
    ):
        """Custom threshold (0.95) should be respected."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_custom_threshold)

        # Score 0.96 should skip with 0.95 threshold
        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context={"messages": []},
            heuristic_score=0.96,
        )

        mock_llm.ainvoke.assert_not_called()
        assert isinstance(result, LLMResponseAnalysis)


# ============================================================================
# TEST CLASS: JSON Parsing
# ============================================================================


class TestLLMResponseAnalyzerParsing:
    """Tests for JSON and text parsing."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_excellent(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_excellent,
        sample_conversation_context_with_rag,
    ):
        """Should correctly parse valid JSON with excellent quality."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_excellent)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.7,
        )

        assert isinstance(result, LLMResponseAnalysis)
        assert result.quality == ResponseQuality.EXCELLENT
        assert result.overall_score == 0.95
        assert result.recommended_action == RecommendedAction.ACCEPT
        assert result.hallucination.risk_level == HallucinationRisk.NONE
        assert result.question_answer_alignment.answers_question is True
        assert result.completeness.is_complete is True

    @pytest.mark.asyncio
    async def test_parse_valid_json_good(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_good,
        sample_conversation_context_with_rag,
    ):
        """Should correctly parse valid JSON with good quality."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_good)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert result.quality == ResponseQuality.GOOD
        assert 0.7 <= result.overall_score <= 0.85
        assert result.recommended_action == RecommendedAction.ACCEPT

    @pytest.mark.asyncio
    async def test_parse_valid_json_partial(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_partial,
        sample_conversation_context_with_rag,
    ):
        """Should correctly parse valid JSON with partial quality."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_partial)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.PARTIAL
        assert result.recommended_action == RecommendedAction.ENHANCE
        assert result.question_answer_alignment.answers_question is False

    @pytest.mark.asyncio
    async def test_parse_json_with_think_tags(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_with_think_tags,
        sample_conversation_context_with_rag,
    ):
        """Should clean <think> tags and parse JSON correctly."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_with_think_tags)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        # Should successfully parse despite <think> tags
        assert isinstance(result, LLMResponseAnalysis)
        assert result.quality == ResponseQuality.GOOD
        assert result.overall_score == 0.8

    @pytest.mark.asyncio
    async def test_parse_malformed_json_fallback_to_text(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_malformed_json,
        sample_conversation_context_with_rag,
    ):
        """Should fallback to text parsing when JSON is malformed."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_malformed_json)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        # Should still return an LLMResponseAnalysis via text parsing
        assert isinstance(result, LLMResponseAnalysis)
        # Text parsing assigns quality based on keywords - "good" is in the text
        assert result.quality in [ResponseQuality.GOOD, ResponseQuality.PARTIAL]

    @pytest.mark.asyncio
    async def test_parse_empty_response(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should handle empty response gracefully."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content="")

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert isinstance(result, LLMResponseAnalysis)
        assert result.quality == ResponseQuality.PARTIAL  # Default for empty

    @pytest.mark.asyncio
    async def test_parse_json_missing_fields_uses_defaults(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should use Pydantic defaults for missing fields."""
        minimal_json = json.dumps({"quality": "good", "overall_score": 0.75})
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=minimal_json)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert result.quality == ResponseQuality.GOOD
        assert result.overall_score == 0.75
        # Defaults applied
        assert result.recommended_action == RecommendedAction.ACCEPT
        assert result.hallucination.risk_level == HallucinationRisk.NONE
        assert result.confidence == 0.8  # Default

    @pytest.mark.asyncio
    async def test_parse_simplified_json_format_v2(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should correctly parse simplified JSON format (v2.0 prompt).

        The v2.0 prompt uses a flat structure with answers_question and
        hallucination_risk at the top level instead of nested objects.
        """
        simplified_json = json.dumps({
            "quality": "partial",
            "overall_score": 0.55,
            "recommended_action": "enhance",
            "answers_question": False,  # Top level instead of nested
            "hallucination_risk": "medium",  # Top level instead of nested
            "reasoning": "Response does not directly answer the question"
        })
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=simplified_json)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Who is the CEO?",
            agent_response="The company was founded in 1990...",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert result.quality == ResponseQuality.PARTIAL
        assert result.overall_score == 0.55
        assert result.recommended_action == RecommendedAction.ENHANCE
        # Should correctly parse top-level fields
        assert result.question_answer_alignment.answers_question is False
        assert result.hallucination.risk_level == HallucinationRisk.MEDIUM
        assert "directly answer" in result.reasoning.lower()


# ============================================================================
# TEST CLASS: Enum Mapping
# ============================================================================


class TestLLMResponseAnalyzerEnumMapping:
    """Tests for enum string-to-enum mapping."""

    @pytest.mark.asyncio
    async def test_quality_mapping_all_values(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should correctly map all quality strings to enums."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        quality_map = {
            "excellent": ResponseQuality.EXCELLENT,
            "good": ResponseQuality.GOOD,
            "partial": ResponseQuality.PARTIAL,
            "insufficient": ResponseQuality.INSUFFICIENT,
            "fallback": ResponseQuality.FALLBACK,
        }

        for quality_str, expected_enum in quality_map.items():
            json_response = json.dumps({"quality": quality_str, "overall_score": 0.5})
            mock_llm.ainvoke.return_value = Mock(content=json_response)

            result = await analyzer.analyze(
                user_message="Test",
                agent_response="Response",
                agent_name="agent",
                conversation_context=sample_conversation_context_with_rag,
                heuristic_score=0.5,
            )

            assert result.quality == expected_enum, f"Failed for quality: {quality_str}"

    @pytest.mark.asyncio
    async def test_quality_mapping_unknown_defaults_to_good(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Unknown quality string should default to GOOD."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        json_response = json.dumps({"quality": "unknown_value", "overall_score": 0.5})
        mock_llm.ainvoke.return_value = Mock(content=json_response)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.GOOD

    @pytest.mark.asyncio
    async def test_action_mapping_reroute_variants(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Both 're_route' and 'reroute' should map to REROUTE."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        for action_str in ["reroute", "re_route"]:
            json_response = json.dumps({
                "quality": "partial",
                "overall_score": 0.5,
                "recommended_action": action_str
            })
            mock_llm.ainvoke.return_value = Mock(content=json_response)

            result = await analyzer.analyze(
                user_message="Test",
                agent_response="Response",
                agent_name="agent",
                conversation_context=sample_conversation_context_with_rag,
                heuristic_score=0.5,
            )

            assert result.recommended_action == RecommendedAction.REROUTE

    @pytest.mark.asyncio
    async def test_hallucination_risk_mapping_all_values(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should correctly map all hallucination risk strings."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        risk_map = {
            "none": HallucinationRisk.NONE,
            "low": HallucinationRisk.LOW,
            "medium": HallucinationRisk.MEDIUM,
            "high": HallucinationRisk.HIGH,
        }

        for risk_str, expected_enum in risk_map.items():
            json_response = json.dumps({
                "quality": "good",
                "overall_score": 0.7,
                "hallucination": {"risk_level": risk_str, "confidence": 0.8}
            })
            mock_llm.ainvoke.return_value = Mock(content=json_response)

            result = await analyzer.analyze(
                user_message="Test",
                agent_response="Response",
                agent_name="agent",
                conversation_context=sample_conversation_context_with_rag,
                heuristic_score=0.5,
            )

            assert result.hallucination.risk_level == expected_enum


# ============================================================================
# TEST CLASS: Hallucination Detection
# ============================================================================


class TestLLMResponseAnalyzerHallucination:
    """Tests for hallucination detection scenarios."""

    @pytest.mark.asyncio
    async def test_hallucination_none_fully_grounded(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_hallucination_none,
        sample_conversation_context_with_rag,
    ):
        """Fully grounded response should have NONE hallucination risk."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_hallucination_none)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Qué incluye el módulo de Inventario?",
            agent_response="El módulo de Inventario incluye control de stock...",
            agent_name="excelencia_agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.7,
        )

        assert result.hallucination.risk_level == HallucinationRisk.NONE
        assert result.hallucination.confidence >= 0.9
        assert len(result.hallucination.suspicious_claims) == 0
        assert len(result.hallucination.grounded_claims) > 0

    @pytest.mark.asyncio
    async def test_hallucination_high_invented_info(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_hallucination_high,
        sample_conversation_context_with_rag,
    ):
        """Response with invented info should have HIGH hallucination risk."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_hallucination_high)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Cuánto cuesta el módulo?",
            agent_response="El precio es $500 USD, incluye soporte 24/7...",
            agent_name="excelencia_agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.hallucination.risk_level == HallucinationRisk.HIGH
        assert len(result.hallucination.suspicious_claims) >= 1
        assert result.has_hallucination_concerns is True

    @pytest.mark.asyncio
    async def test_hallucination_medium_some_ungrounded(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_json_hallucination_medium,
        sample_conversation_context_with_rag,
    ):
        """Response with some ungrounded claims should have MEDIUM risk."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_json_hallucination_medium)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Cuánto tiempo toma la entrega?",
            agent_response="La entrega demora 2 días...",
            agent_name="excelencia_agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert result.hallucination.risk_level == HallucinationRisk.MEDIUM
        assert result.has_hallucination_concerns is True

    @pytest.mark.asyncio
    async def test_hallucination_invented_prices(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should detect invented price information."""
        json_response = json.dumps({
            "quality": "partial",
            "overall_score": 0.4,
            "recommended_action": "reroute",
            "hallucination": {
                "risk_level": "high",
                "suspicious_claims": ["El módulo cuesta $299.99 USD mensuales"],
                "grounded_claims": [],
                "confidence": 0.9
            }
        })
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=json_response)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Cuánto cuesta?",
            agent_response="El módulo cuesta $299.99 USD mensuales",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.hallucination.risk_level == HallucinationRisk.HIGH
        assert any("$299.99" in claim for claim in result.hallucination.suspicious_claims)

    @pytest.mark.asyncio
    async def test_hallucination_invented_features(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should detect invented feature claims."""
        json_response = json.dumps({
            "quality": "partial",
            "overall_score": 0.45,
            "recommended_action": "reroute",
            "hallucination": {
                "risk_level": "high",
                "suspicious_claims": [
                    "Integración automática con SAP",
                    "Soporte para blockchain"
                ],
                "grounded_claims": [],
                "confidence": 0.88
            }
        })
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=json_response)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Qué integraciones tiene?",
            agent_response="Integra con SAP y soporta blockchain",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.hallucination.risk_level == HallucinationRisk.HIGH
        assert len(result.hallucination.suspicious_claims) >= 2

    @pytest.mark.asyncio
    async def test_hallucination_rag_empty_detailed_response(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_empty,
    ):
        """Detailed response with empty RAG should raise suspicion."""
        json_response = json.dumps({
            "quality": "partial",
            "overall_score": 0.35,
            "recommended_action": "reroute",
            "hallucination": {
                "risk_level": "high",
                "suspicious_claims": [
                    "All specific details provided without RAG support"
                ],
                "grounded_claims": [],
                "confidence": 0.85
            }
        })
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=json_response)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="¿Detalles del producto?",
            agent_response="El producto tiene características X, Y, Z con precio $100",
            agent_name="agent",
            conversation_context=sample_conversation_context_empty,
            heuristic_score=0.4,
        )

        assert result.hallucination.risk_level == HallucinationRisk.HIGH

    @pytest.mark.asyncio
    async def test_hallucination_claims_extraction(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should properly extract suspicious and grounded claims."""
        json_response = json.dumps({
            "quality": "good",
            "overall_score": 0.7,
            "recommended_action": "enhance",
            "hallucination": {
                "risk_level": "medium",
                "suspicious_claims": [
                    "El precio es $500",
                    "Entrega en 24 horas"
                ],
                "grounded_claims": [
                    "El sistema incluye facturación",
                    "Soporta CFDI 4.0"
                ],
                "confidence": 0.75
            }
        })
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=json_response)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Info del sistema",
            agent_response="El sistema...",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert len(result.hallucination.suspicious_claims) == 2
        assert len(result.hallucination.grounded_claims) == 2
        assert "El precio es $500" in result.hallucination.suspicious_claims
        assert "Soporta CFDI 4.0" in result.hallucination.grounded_claims


# ============================================================================
# TEST CLASS: Error Handling
# ============================================================================


class TestLLMResponseAnalyzerErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_llm_exception_returns_fallback(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """LLM exception should return AnalyzerFallbackResult."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.side_effect = Exception("LLM connection failed")

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.6,
        )

        assert isinstance(result, AnalyzerFallbackResult)
        assert result.used_fallback is True
        assert "failed" in result.reason.lower()
        assert result.heuristic_score == 0.6

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_fallback(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Timeout from asyncio.wait_for should return AnalyzerFallbackResult with timeout reason."""
        import asyncio

        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.side_effect = asyncio.TimeoutError("Request timed out")

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert isinstance(result, AnalyzerFallbackResult)
        assert result.used_fallback is True
        # New: Should include timeout in reason
        assert "timeout" in result.reason.lower()
        assert result.heuristic_score == 0.5

    @pytest.mark.asyncio
    async def test_llm_timeout_custom_timeout_value(
        self,
        mock_ollama_with_llm,
        sample_conversation_context_with_rag,
    ):
        """Should use custom timeout value from config."""
        import asyncio

        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.side_effect = asyncio.TimeoutError("Timeout")

        # Use custom timeout of 5 seconds
        analyzer = LLMResponseAnalyzer(
            ollama=mock_ollama,
            config={"enable_llm_analysis": True, "llm_timeout": 5}
        )

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert isinstance(result, AnalyzerFallbackResult)
        # Reason should mention the custom timeout value
        assert "5s" in result.reason

    @pytest.mark.asyncio
    async def test_llm_returns_none_content(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """
        LLM returning None content should be handled gracefully.

        FIX APPLIED: _clean_think_tags now returns empty string for None,
        and _parse_text_response handles empty text gracefully.
        """
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=None)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        # After fix: Should handle gracefully and return LLMResponseAnalysis
        assert isinstance(result, LLMResponseAnalysis)
        # Empty text defaults to PARTIAL quality
        assert result.quality == ResponseQuality.PARTIAL

    @pytest.mark.asyncio
    async def test_llm_returns_none_response(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """LLM returning None should be handled."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = None

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        # Should handle gracefully
        assert isinstance(result, LLMResponseAnalysis)

    @pytest.mark.asyncio
    async def test_heuristic_score_none_uses_default(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
    ):
        """When heuristic_score is None, should use default."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.side_effect = Exception("Error")

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context={"messages": []},
            heuristic_score=None,  # None
        )

        assert isinstance(result, AnalyzerFallbackResult)
        assert result.heuristic_score == 0.5  # Default


# ============================================================================
# TEST CLASS: Text Parsing Fallback
# ============================================================================


class TestLLMResponseAnalyzerTextParsing:
    """Tests for text parsing fallback when JSON fails."""

    @pytest.mark.asyncio
    async def test_text_parse_excellent_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_text_excellent,
        sample_conversation_context_with_rag,
    ):
        """Should detect excellent quality from text keywords."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_text_excellent)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.EXCELLENT
        assert result.overall_score == 0.9

    @pytest.mark.asyncio
    async def test_text_parse_reroute_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_text_reroute,
        sample_conversation_context_with_rag,
    ):
        """Should detect reroute action from text keywords."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_text_reroute)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.recommended_action == RecommendedAction.REROUTE

    @pytest.mark.asyncio
    async def test_text_parse_escalate_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_text_escalate,
        sample_conversation_context_with_rag,
    ):
        """Should detect escalate action from text keywords."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_text_escalate)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.recommended_action == RecommendedAction.ESCALATE

    @pytest.mark.asyncio
    async def test_text_parse_hallucination_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_llm_text_hallucination,
        sample_conversation_context_with_rag,
    ):
        """Should detect high hallucination from text keywords."""
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=sample_llm_text_hallucination)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.hallucination.risk_level == HallucinationRisk.HIGH

    @pytest.mark.asyncio
    async def test_text_parse_good_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """Should detect good quality from text keywords."""
        text = "The response is mostly adequate and satisfactory for the user's needs."
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=text)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.GOOD
        assert result.overall_score == 0.75

    @pytest.mark.asyncio
    async def test_text_parse_partial_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """
        Should detect partial quality from text keywords.

        FIX APPLIED: Keyword priority now checks negative patterns first,
        so "incomplete" correctly matches PARTIAL instead of EXCELLENT.
        """
        # After fix: "incomplete" should correctly match PARTIAL
        text = "The response is partial and incomplete, missing key information."
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=text)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.PARTIAL
        assert result.overall_score == 0.5

    @pytest.mark.asyncio
    async def test_text_parse_insufficient_keywords(
        self,
        mock_ollama_with_llm,
        analyzer_config_enabled,
        sample_conversation_context_with_rag,
    ):
        """
        Should detect insufficient quality from text keywords.

        FIX APPLIED: Keyword priority now checks negative patterns first,
        so "inadequate" correctly matches INSUFFICIENT instead of GOOD.
        """
        # After fix: "inadequate" should correctly match INSUFFICIENT
        text = "The response is insufficient and inadequate. It fails to address the question."
        mock_ollama, mock_llm = mock_ollama_with_llm
        mock_llm.ainvoke.return_value = Mock(content=text)

        analyzer = LLMResponseAnalyzer(ollama=mock_ollama, config=analyzer_config_enabled)

        result = await analyzer.analyze(
            user_message="Test",
            agent_response="Response",
            agent_name="agent",
            conversation_context=sample_conversation_context_with_rag,
            heuristic_score=0.5,
        )

        assert result.quality == ResponseQuality.INSUFFICIENT
        assert result.overall_score == 0.3


# ============================================================================
# TEST CLASS: Conversation Summary
# ============================================================================


class TestLLMResponseAnalyzerConversationSummary:
    """Tests for conversation summary building."""

    def test_summary_empty_messages(self):
        """Empty messages should return beginning of conversation message."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        summary = analyzer._build_conversation_summary([])
        assert "beginning" in summary.lower()

    def test_summary_few_messages(self):
        """
        Few messages behavior.

        Implementation note: len(messages) <= 2 returns "beginning of conversation"
        because it excludes the last message (being evaluated), leaving only 1 message.
        """
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        # With 2 messages, after excluding last one, only 1 remains = beginning
        messages_2 = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
        ]
        summary_2 = analyzer._build_conversation_summary(messages_2)
        assert "beginning" in summary_2.lower()

        # With 3+ messages, we get actual content
        messages_3 = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]
        summary_3 = analyzer._build_conversation_summary(messages_3)
        assert "Question 1" in summary_3

    def test_summary_many_messages_truncated(self):
        """Many messages should be truncated to last 6."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"Question {i}"})
            messages.append({"role": "assistant", "content": f"Answer {i}"})

        summary = analyzer._build_conversation_summary(messages)
        # Should only have last 6 messages (excluding the one being evaluated)
        assert "Question 0" not in summary  # Too old
        assert "Question 1" not in summary  # Too old

    def test_summary_long_content_truncated(self):
        """Long message content should be truncated to 150 chars."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        # Need 3+ messages to get actual summary (not "beginning of conversation")
        long_content = "A" * 200  # 200 chars
        messages = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},  # This will be excluded
        ]
        summary = analyzer._build_conversation_summary(messages)
        # Should be truncated with "..."
        assert "..." in summary
        # First line should have truncated content
        first_line = summary.split("\n")[0]
        assert "user:" in first_line.lower()
        # Content should be truncated
        assert len(first_line) < 200


# ============================================================================
# TEST CLASS: LLMResponseAnalysis Properties
# ============================================================================


class TestLLMResponseAnalysisProperties:
    """Tests for LLMResponseAnalysis model properties."""

    def test_needs_action_accept(self):
        """ACCEPT action should not need action."""
        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.GOOD,
            overall_score=0.8,
            recommended_action=RecommendedAction.ACCEPT,
        )
        assert analysis.needs_action is False

    def test_needs_action_other(self):
        """Non-ACCEPT actions should need action."""
        for action in [
            RecommendedAction.ENHANCE,
            RecommendedAction.REROUTE,
            RecommendedAction.CLARIFY,
            RecommendedAction.ESCALATE,
        ]:
            analysis = LLMResponseAnalysis(
                quality=ResponseQuality.PARTIAL,
                overall_score=0.5,
                recommended_action=action,
            )
            assert analysis.needs_action is True

    def test_is_acceptable_excellent(self):
        """EXCELLENT quality should be acceptable."""
        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.EXCELLENT,
            overall_score=0.95,
        )
        assert analysis.is_acceptable is True

    def test_is_acceptable_good(self):
        """GOOD quality should be acceptable."""
        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.GOOD,
            overall_score=0.8,
        )
        assert analysis.is_acceptable is True

    def test_is_acceptable_partial(self):
        """PARTIAL quality should not be acceptable."""
        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.PARTIAL,
            overall_score=0.5,
        )
        assert analysis.is_acceptable is False

    def test_has_hallucination_concerns_high(self):
        """HIGH hallucination should have concerns."""
        from app.core.graph.agents.supervisor.schemas.analyzer_schemas import HallucinationAnalysis

        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.PARTIAL,
            overall_score=0.5,
            hallucination=HallucinationAnalysis(risk_level=HallucinationRisk.HIGH),
        )
        assert analysis.has_hallucination_concerns is True

    def test_has_hallucination_concerns_medium(self):
        """MEDIUM hallucination should have concerns."""
        from app.core.graph.agents.supervisor.schemas.analyzer_schemas import HallucinationAnalysis

        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.GOOD,
            overall_score=0.7,
            hallucination=HallucinationAnalysis(risk_level=HallucinationRisk.MEDIUM),
        )
        assert analysis.has_hallucination_concerns is True

    def test_has_hallucination_concerns_low(self):
        """LOW hallucination should not have concerns."""
        from app.core.graph.agents.supervisor.schemas.analyzer_schemas import HallucinationAnalysis

        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.GOOD,
            overall_score=0.8,
            hallucination=HallucinationAnalysis(risk_level=HallucinationRisk.LOW),
        )
        assert analysis.has_hallucination_concerns is False

    def test_to_evaluation_dict(self):
        """Should convert to evaluation dict format."""
        from app.core.graph.agents.supervisor.schemas.analyzer_schemas import (
            CompletenessAnalysis,
            HallucinationAnalysis,
            QuestionAnswerAlignment,
        )

        analysis = LLMResponseAnalysis(
            quality=ResponseQuality.GOOD,
            overall_score=0.8,
            recommended_action=RecommendedAction.ACCEPT,
            reasoning="Test reasoning",
            confidence=0.85,
            question_answer_alignment=QuestionAnswerAlignment(answers_question=True),
            completeness=CompletenessAnalysis(is_complete=True, has_specific_data=True),
            hallucination=HallucinationAnalysis(risk_level=HallucinationRisk.NONE),
        )

        eval_dict = analysis.to_evaluation_dict()

        assert eval_dict["llm_quality"] == "good"
        assert eval_dict["llm_score"] == 0.8
        assert eval_dict["llm_recommended_action"] == "accept"
        assert eval_dict["llm_reasoning"] == "Test reasoning"
        assert eval_dict["llm_confidence"] == 0.85
        assert eval_dict["hallucination_risk"] == "none"
        assert eval_dict["question_answered"] is True
        assert eval_dict["is_complete"] is True
        assert eval_dict["has_specific_data"] is True


# ============================================================================
# TEST CLASS: AnalyzerFallbackResult
# ============================================================================


class TestAnalyzerFallbackResult:
    """Tests for AnalyzerFallbackResult model."""

    def test_fallback_result_creation(self):
        """Should create fallback result correctly."""
        result = AnalyzerFallbackResult(
            reason="LLM timeout",
            heuristic_score=0.7,
        )
        assert result.used_fallback is True
        assert result.reason == "LLM timeout"
        assert result.heuristic_score == 0.7
        assert result.recommended_action == RecommendedAction.ACCEPT

    def test_fallback_result_to_evaluation_dict(self):
        """Should convert to evaluation dict format."""
        result = AnalyzerFallbackResult(
            reason="No LLM instance",
            heuristic_score=0.65,
        )

        eval_dict = result.to_evaluation_dict()

        assert eval_dict["llm_analysis_status"] == "fallback"
        assert eval_dict["llm_fallback_reason"] == "No LLM instance"
        assert eval_dict["heuristic_score"] == 0.65


# ============================================================================
# TEST CLASS: Clean Think Tags
# ============================================================================


class TestCleanThinkTags:
    """Tests for <think> tag cleaning."""

    def test_clean_single_think_block(self):
        """Should remove single <think> block."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        text = "<think>Internal reasoning here</think>Actual response"
        cleaned = analyzer._clean_think_tags(text)
        assert "<think>" not in cleaned
        assert "</think>" not in cleaned
        assert "Actual response" in cleaned

    def test_clean_multiple_think_blocks(self):
        """Should remove multiple <think> blocks."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        text = "<think>First</think>Middle<think>Second</think>End"
        cleaned = analyzer._clean_think_tags(text)
        assert "<think>" not in cleaned
        assert "MiddleEnd" in cleaned.replace(" ", "")

    def test_clean_multiline_think_block(self):
        """Should remove multiline <think> block."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        text = """<think>
        Line 1
        Line 2
        Line 3
        </think>
        {"quality": "good"}"""
        cleaned = analyzer._clean_think_tags(text)
        assert "<think>" not in cleaned
        assert '{"quality": "good"}' in cleaned

    def test_clean_no_think_tags(self):
        """Should return unchanged if no <think> tags."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        text = '{"quality": "good"}'
        cleaned = analyzer._clean_think_tags(text)
        assert cleaned == text

    def test_clean_empty_string(self):
        """Should handle empty string."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        cleaned = analyzer._clean_think_tags("")
        assert cleaned == ""

    def test_clean_none_input(self):
        """Should handle None input by returning empty string."""
        analyzer = LLMResponseAnalyzer(ollama=None, config={"enable_llm_analysis": False})
        cleaned = analyzer._clean_think_tags(None)
        # After fix: Returns empty string instead of None to prevent downstream errors
        assert cleaned == ""
