"""
Fixtures for Supervisor Agent unit tests.

Provides mock objects and sample data for testing:
- LLMResponseAnalyzer
- ResponseQualityEvaluator integration
- SupervisorAgent integration

Uses vLLM as the LLM backend.
"""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest


# ============================================================================
# LLM FIXTURES
# ============================================================================


@pytest.fixture
def mock_llm_with_llm():
    """
    Create a mock VllmLLM instance that returns a mock LLM.

    Returns:
        Tuple of (mock_llm_provider, mock_llm) for configuring LLM responses
    """
    mock_llm_provider = MagicMock()
    mock_llm = AsyncMock()
    mock_llm_provider.get_llm.return_value = mock_llm
    return mock_llm_provider, mock_llm


@pytest.fixture
def mock_llm_disabled():
    """Return None to simulate disabled LLM."""
    return None


# ============================================================================
# LLM JSON RESPONSE FIXTURES
# ============================================================================


@pytest.fixture
def sample_llm_json_excellent():
    """Sample JSON response for EXCELLENT quality."""
    return json.dumps({
        "quality": "excellent",
        "overall_score": 0.95,
        "recommended_action": "accept",
        "question_answer_alignment": {
            "answers_question": True,
            "alignment_score": 0.95,
            "missing_aspects": [],
            "extra_information": False
        },
        "completeness": {
            "is_complete": True,
            "completeness_score": 0.95,
            "missing_information": [],
            "has_specific_data": True
        },
        "hallucination": {
            "risk_level": "none",
            "suspicious_claims": [],
            "grounded_claims": ["El módulo de Inventario permite control de stock"],
            "confidence": 0.95
        },
        "uses_conversation_context": True,
        "appropriate_for_agent": True,
        "reasoning": "Response fully answers the question with specific data from RAG",
        "confidence": 0.92
    })


@pytest.fixture
def sample_llm_json_good():
    """Sample JSON response for GOOD quality."""
    return json.dumps({
        "quality": "good",
        "overall_score": 0.78,
        "recommended_action": "accept",
        "question_answer_alignment": {
            "answers_question": True,
            "alignment_score": 0.8,
            "missing_aspects": ["pricing details"],
            "extra_information": False
        },
        "completeness": {
            "is_complete": True,
            "completeness_score": 0.75,
            "missing_information": ["specific pricing"],
            "has_specific_data": True
        },
        "hallucination": {
            "risk_level": "low",
            "suspicious_claims": [],
            "grounded_claims": ["El sistema incluye reportes"],
            "confidence": 0.85
        },
        "uses_conversation_context": True,
        "appropriate_for_agent": True,
        "reasoning": "Response is mostly complete but lacks some details",
        "confidence": 0.82
    })


@pytest.fixture
def sample_llm_json_partial():
    """Sample JSON response for PARTIAL quality."""
    return json.dumps({
        "quality": "partial",
        "overall_score": 0.55,
        "recommended_action": "enhance",
        "question_answer_alignment": {
            "answers_question": False,
            "alignment_score": 0.5,
            "missing_aspects": ["main question not addressed", "specific features"],
            "extra_information": False
        },
        "completeness": {
            "is_complete": False,
            "completeness_score": 0.5,
            "missing_information": ["key functionality details", "pricing"],
            "has_specific_data": False
        },
        "hallucination": {
            "risk_level": "low",
            "suspicious_claims": [],
            "grounded_claims": [],
            "confidence": 0.7
        },
        "uses_conversation_context": False,
        "appropriate_for_agent": True,
        "reasoning": "Response is incomplete and doesn't fully address the question",
        "confidence": 0.75
    })


@pytest.fixture
def sample_llm_json_insufficient():
    """Sample JSON response for INSUFFICIENT quality."""
    return json.dumps({
        "quality": "insufficient",
        "overall_score": 0.35,
        "recommended_action": "reroute",
        "question_answer_alignment": {
            "answers_question": False,
            "alignment_score": 0.3,
            "missing_aspects": ["entire question not addressed"],
            "extra_information": False
        },
        "completeness": {
            "is_complete": False,
            "completeness_score": 0.3,
            "missing_information": ["all requested information"],
            "has_specific_data": False
        },
        "hallucination": {
            "risk_level": "medium",
            "suspicious_claims": ["some unsupported claims"],
            "grounded_claims": [],
            "confidence": 0.6
        },
        "uses_conversation_context": False,
        "appropriate_for_agent": False,
        "reasoning": "Response fails to address the user's question adequately",
        "confidence": 0.7
    })


@pytest.fixture
def sample_llm_json_fallback():
    """Sample JSON response for FALLBACK quality (generic response)."""
    return json.dumps({
        "quality": "fallback",
        "overall_score": 0.2,
        "recommended_action": "reroute",
        "question_answer_alignment": {
            "answers_question": False,
            "alignment_score": 0.1,
            "missing_aspects": ["everything"],
            "extra_information": False
        },
        "completeness": {
            "is_complete": False,
            "completeness_score": 0.1,
            "missing_information": ["all information"],
            "has_specific_data": False
        },
        "hallucination": {
            "risk_level": "none",
            "suspicious_claims": [],
            "grounded_claims": [],
            "confidence": 0.9
        },
        "uses_conversation_context": False,
        "appropriate_for_agent": False,
        "reasoning": "Generic fallback response with no useful information",
        "confidence": 0.85
    })


# ============================================================================
# HALLUCINATION-SPECIFIC FIXTURES
# ============================================================================


@pytest.fixture
def sample_llm_json_hallucination_high():
    """Sample JSON response with HIGH hallucination risk."""
    return json.dumps({
        "quality": "partial",
        "overall_score": 0.4,
        "recommended_action": "reroute",
        "question_answer_alignment": {
            "answers_question": True,
            "alignment_score": 0.6,
            "missing_aspects": [],
            "extra_information": True
        },
        "completeness": {
            "is_complete": True,
            "completeness_score": 0.7,
            "missing_information": [],
            "has_specific_data": True
        },
        "hallucination": {
            "risk_level": "high",
            "suspicious_claims": [
                "El precio del módulo es $500 USD",
                "Incluye soporte 24/7",
                "Integra con SAP automáticamente"
            ],
            "grounded_claims": ["Excelencia es un software ERP"],
            "confidence": 0.88
        },
        "uses_conversation_context": False,
        "appropriate_for_agent": True,
        "reasoning": "Response contains fabricated pricing and feature claims not in RAG",
        "confidence": 0.85
    })


@pytest.fixture
def sample_llm_json_hallucination_medium():
    """Sample JSON response with MEDIUM hallucination risk."""
    return json.dumps({
        "quality": "good",
        "overall_score": 0.65,
        "recommended_action": "enhance",
        "question_answer_alignment": {
            "answers_question": True,
            "alignment_score": 0.7,
            "missing_aspects": [],
            "extra_information": True
        },
        "completeness": {
            "is_complete": True,
            "completeness_score": 0.75,
            "missing_information": [],
            "has_specific_data": True
        },
        "hallucination": {
            "risk_level": "medium",
            "suspicious_claims": [
                "La entrega demora aproximadamente 2 días"
            ],
            "grounded_claims": [
                "El módulo de facturación permite generar CFDI",
                "Incluye reportes mensuales"
            ],
            "confidence": 0.7
        },
        "uses_conversation_context": True,
        "appropriate_for_agent": True,
        "reasoning": "Some claims lack grounding but core information is correct",
        "confidence": 0.72
    })


@pytest.fixture
def sample_llm_json_hallucination_none():
    """Sample JSON response with NO hallucination risk (fully grounded)."""
    return json.dumps({
        "quality": "excellent",
        "overall_score": 0.92,
        "recommended_action": "accept",
        "question_answer_alignment": {
            "answers_question": True,
            "alignment_score": 0.95,
            "missing_aspects": [],
            "extra_information": False
        },
        "completeness": {
            "is_complete": True,
            "completeness_score": 0.9,
            "missing_information": [],
            "has_specific_data": True
        },
        "hallucination": {
            "risk_level": "none",
            "suspicious_claims": [],
            "grounded_claims": [
                "El módulo de Inventario incluye control de stock",
                "Permite generar reportes de existencias",
                "Soporta múltiples almacenes"
            ],
            "confidence": 0.95
        },
        "uses_conversation_context": True,
        "appropriate_for_agent": True,
        "reasoning": "All claims are fully grounded in RAG context",
        "confidence": 0.93
    })


# ============================================================================
# MALFORMED / EDGE CASE JSON FIXTURES
# ============================================================================


@pytest.fixture
def sample_llm_json_with_think_tags():
    """Sample response with deepseek-r1 <think> tags."""
    return """<think>
Let me analyze this response carefully.
The user asked about pricing.
The response mentions specific features.
I need to check if claims are grounded.
</think>

{
    "quality": "good",
    "overall_score": 0.8,
    "recommended_action": "accept",
    "question_answer_alignment": {
        "answers_question": true,
        "alignment_score": 0.8,
        "missing_aspects": [],
        "extra_information": false
    },
    "completeness": {
        "is_complete": true,
        "completeness_score": 0.8,
        "missing_information": [],
        "has_specific_data": true
    },
    "hallucination": {
        "risk_level": "none",
        "suspicious_claims": [],
        "grounded_claims": ["Feature X is available"],
        "confidence": 0.85
    },
    "uses_conversation_context": true,
    "appropriate_for_agent": true,
    "reasoning": "Good response with grounded claims",
    "confidence": 0.82
}"""


@pytest.fixture
def sample_llm_malformed_json():
    """Sample malformed JSON (missing closing brace)."""
    return """{
    "quality": "good",
    "overall_score": 0.8,
    "recommended_action": "accept"
"""


@pytest.fixture
def sample_llm_text_excellent():
    """Sample text response (no JSON) indicating excellent quality."""
    return """The response is excellent and fully complete.
It directly answers the user's question with specific data.
All claims are grounded in the RAG context.
No hallucination detected. The agent is appropriate for this query."""


@pytest.fixture
def sample_llm_text_reroute():
    """Sample text response suggesting reroute to different agent."""
    return """The response is insufficient. A different agent should handle this.
The user asked about invoicing but the product agent responded.
Recommend rerouting to the invoice agent for better results."""


@pytest.fixture
def sample_llm_text_escalate():
    """Sample text response suggesting escalation to human."""
    return """The user appears frustrated and needs human intervention.
The response fails to address their concerns.
I recommend escalating to a human supervisor for proper handling."""


@pytest.fixture
def sample_llm_text_hallucination():
    """Sample text response detecting high hallucination."""
    return """The response contains high hallucination risk.
Several claims appear to be fabricated or invented.
The pricing mentioned is not in the RAG context.
High confidence that information is not accurate."""


# ============================================================================
# CONVERSATION CONTEXT FIXTURES
# ============================================================================


@pytest.fixture
def sample_conversation_context_empty():
    """Empty conversation context (start of conversation)."""
    return {
        "messages": [],
        "rag_context": "",
        "rag_metrics": {"has_results": False}
    }


@pytest.fixture
def sample_conversation_context_with_rag():
    """Conversation context with RAG results."""
    return {
        "messages": [
            {"role": "user", "content": "¿Qué módulos tiene Excelencia?"},
            {"role": "assistant", "content": "Excelencia tiene varios módulos..."}
        ],
        "rag_context": """
        Excelencia ERP incluye los siguientes módulos:
        - Inventario: Control de stock, entradas y salidas
        - Facturación: Generación de CFDI 4.0
        - Contabilidad: Registros contables y reportes
        - Cuentas por Cobrar: Gestión de cartera
        """,
        "rag_metrics": {"has_results": True, "top_score": 0.85}
    }


@pytest.fixture
def sample_conversation_context_long():
    """Conversation context with many messages (test truncation)."""
    messages = []
    for i in range(10):
        messages.append({"role": "user", "content": f"Pregunta {i}: ¿Información sobre tema {i}?"})
        messages.append({"role": "assistant", "content": f"Respuesta {i}: Aquí está la información..."})

    return {
        "messages": messages,
        "rag_context": "Some RAG context here",
        "rag_metrics": {"has_results": True}
    }


@pytest.fixture
def sample_conversation_context_long_message():
    """Conversation context with a very long message (test truncation)."""
    long_content = "A" * 200  # 200 chars, should be truncated to 150
    return {
        "messages": [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "Short response"}
        ],
        "rag_context": "",
        "rag_metrics": {"has_results": False}
    }


# ============================================================================
# ANALYZER CONFIG FIXTURES
# ============================================================================


@pytest.fixture
def analyzer_config_enabled():
    """Config with LLM analysis enabled (default threshold 0.90)."""
    return {
        "enable_llm_analysis": True,
        "llm_timeout": 15,  # Updated to match new default
        "skip_llm_threshold": 0.90  # Updated to match new default
    }


@pytest.fixture
def analyzer_config_disabled():
    """Config with LLM analysis disabled."""
    return {
        "enable_llm_analysis": False,
        "llm_timeout": 15,
        "skip_llm_threshold": 0.90
    }


@pytest.fixture
def analyzer_config_custom_threshold():
    """Config with custom skip threshold (higher than default)."""
    return {
        "enable_llm_analysis": True,
        "llm_timeout": 60,
        "skip_llm_threshold": 0.95  # Higher threshold for testing custom config
    }


# ============================================================================
# HEURISTIC EVALUATION FIXTURES
# ============================================================================


@pytest.fixture
def sample_heuristic_evaluation_high():
    """Sample heuristic evaluation with high score."""
    return {
        "overall_score": 0.85,
        "category": "COMPLETE_WITH_DATA",
        "suggested_action": "accept",
        "scores": {
            "completeness": 0.9,
            "relevance": 0.85,
            "clarity": 0.8,
            "helpfulness": 0.85
        },
        "has_specific_data": True,
        "is_fallback": False
    }


@pytest.fixture
def sample_heuristic_evaluation_medium():
    """Sample heuristic evaluation with medium score."""
    return {
        "overall_score": 0.65,
        "category": "PARTIAL_INFO",
        "suggested_action": "enhance",
        "scores": {
            "completeness": 0.6,
            "relevance": 0.7,
            "clarity": 0.65,
            "helpfulness": 0.6
        },
        "has_specific_data": True,
        "is_fallback": False
    }


@pytest.fixture
def sample_heuristic_evaluation_low():
    """Sample heuristic evaluation with low score (fallback)."""
    return {
        "overall_score": 0.35,
        "category": "FALLBACK_RESPONSE",
        "suggested_action": "re_route",
        "scores": {
            "completeness": 0.3,
            "relevance": 0.4,
            "clarity": 0.35,
            "helpfulness": 0.3
        },
        "has_specific_data": False,
        "is_fallback": True
    }


# ============================================================================
# SAMPLE USER MESSAGES AND AGENT RESPONSES
# ============================================================================


@pytest.fixture
def sample_user_message():
    """Sample user question."""
    return "¿Cuáles son los módulos disponibles en Excelencia?"


@pytest.fixture
def sample_agent_response_complete():
    """Sample complete agent response."""
    return """Excelencia cuenta con los siguientes módulos principales:

1. **Inventario**: Control de stock, entradas, salidas y traspasos
2. **Facturación**: Generación de CFDI 4.0 con timbrado automático
3. **Contabilidad**: Pólizas, balanza de comprobación y estados financieros
4. **Cuentas por Cobrar**: Gestión de cartera y cobranza

¿Te gustaría conocer más detalles de algún módulo en particular?"""


@pytest.fixture
def sample_agent_response_fallback():
    """Sample fallback/generic agent response."""
    return """No encontré información específica sobre tu consulta.
Te recomiendo contactar a nuestro equipo de soporte para más información.
¿Puedo ayudarte con algo más?"""


@pytest.fixture
def sample_agent_response_with_hallucination():
    """Sample agent response with potential hallucinations."""
    return """El módulo de Inventario de Excelencia tiene un costo de $500 USD mensuales.
Incluye soporte técnico 24/7 y actualizaciones automáticas.
También se integra automáticamente con SAP y Oracle.
La implementación toma solo 2 días."""
