"""Keyword-based intent detection (fallback analyzer).

Extracted from IntentRouter to follow Single Responsibility Principle.
Used as last resort when LLM and SpaCy analysis fail.
"""

import logging
from typing import Any

from app.core.intelligence.validators.intent_validator import IntentValidator

logger = logging.getLogger(__name__)


class KeywordIntentAnalyzer:
    """Keyword-based intent detection using pattern matching.

    This is the fallback analyzer used when LLM and SpaCy are unavailable
    or return low confidence results.

    Pattern Matching:
    - Scores messages based on keyword matches
    - Higher match count = higher confidence
    - Returns fallback intent if no patterns match
    """

    # Keyword patterns by intent category
    KEYWORD_PATTERNS: dict[str, list[str]] = {
        "saludo": [
            "hola",
            "buenos días",
            "buenas tardes",
            "buenas noches",
            "saludos",
            "hey",
            "hi",
            "hello",
            "qué tal",
            "cómo estás",
        ],
        "producto": [
            "producto",
            "productos",
            "stock",
            "precio",
            "cuesta",
            "venden",
            "tienen",
            "catálogo",
            "disponible",
        ],
        # E-commerce intents
        "promociones": [
            "oferta",
            "ofertas",
            "descuento",
            "promoción",
            "cupón",
            "rebaja",
            "barato",
        ],
        "seguimiento": [
            "pedido",
            "orden",
            "envío",
            "tracking",
            "seguimiento",
            "dónde está",
            "cuando llega",
        ],
        "facturacion": [
            "factura pedido",
            "recibo",
            "pago",
            "cobro",
            "reembolso",
            "devolver",
            "cancelar",
        ],
        "categoria": [
            "categoría",
            "tipo",
            "tecnología",
            "ropa",
            "zapatos",
            "televisores",
            "laptops",
        ],
        # Excelencia-specific intents
        "excelencia_facturacion": [
            "factura cliente",
            "factura de cliente",
            "estado de cuenta",
            "cobranza",
            "cobrar cliente",
            "deuda cliente",
            "pago cliente",
            "facturar cliente",
            "generar factura cliente",
        ],
        "excelencia_promociones": [
            "promoción software",
            "descuento módulo",
            "oferta implementación",
            "promoción excelencia",
            "descuento capacitación",
            "promo software",
            "oferta software",
            "descuento software",
        ],
        "excelencia": [
            "excelencia",
            "excelencia digital",
            "misión",
            "visión",
            "erp",
            "demo",
            "módulo",
            "módulos",
            "software",
            "turnos médicos",
            "historia clínica",
            "healthcare",
            "hotel",
            "hoteles",
            "obras sociales",
            "gremio",
            "gremios",
            "capacitación",
            "zismed",
            "ai medassist",
            "turmedica",
            "mediflow",
            "medicpay",
            "finflow",
            "validtek",
            "farmatek",
            "inroom",
            "lumenai",
            "gremiocash",
        ],
        # Excelencia Software Support/Incidents
        "excelencia_soporte": [
            "incidencia",
            "reportar",
            "ticket",
            "falla",
            "bug",
            "levantar ticket",
            "problema módulo",
            "error sistema",
            "error interno",
            "zismed",
            "turmedica",
            "mediflow",
            "medicpay",
            "finflow",
            "validtek",
            "farmatek",
            "inroom",
            "lumenai",
            "gremiocash",
            "ai medassist",
            "turno",
            "turnos",
        ],
        # General support
        "soporte": [
            "problema producto",
            "error envío",
            "ayuda pedido",
            "reclamo compra",
            "defectuoso",
        ],
        "despedida": [
            "adiós",
            "chau",
            "bye",
            "gracias",
            "eso es todo",
            "hasta luego",
            "nada más",
        ],
    }

    def __init__(self, validator: IntentValidator):
        """Initialize with validator for agent mapping.

        Args:
            validator: IntentValidator instance for mapping intents to agents
        """
        self._validator = validator

    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze message using keyword pattern matching.

        Args:
            message: User message to analyze
            context: Optional context (unused in keyword analysis)

        Returns:
            Intent result dict
        """
        logger.debug(f"Keyword fallback for: {message[:30]}...")

        message_lower = message.lower()

        # Calculate scores for each intent
        scores: dict[str, int] = {}
        for intent, keywords in self.KEYWORD_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            scores[intent] = score

        # Find best match
        if scores and max(scores.values()) > 0:
            best_intent, match_count = max(scores.items(), key=lambda x: x[1])

            # Confidence based on match count
            # 1 match = 0.5, 2 matches = 0.65, 3+ matches = 0.8 (max)
            confidence = min(0.5 + (match_count * 0.15), 0.8)

            return {
                "primary_intent": best_intent,
                "intent": best_intent,
                "confidence": confidence,
                "entities": [],
                "requires_handoff": False,
                "target_agent": self._validator.map_intent_to_agent(best_intent),
                "method": self.get_method_name(),
                "reasoning": f"Keyword match: {match_count} keywords found for '{best_intent}'",
            }

        # No keyword match - use fallback
        return {
            "primary_intent": "fallback",
            "intent": "fallback",
            "confidence": 0.4,
            "entities": [],
            "requires_handoff": False,
            "target_agent": "fallback_agent",
            "method": self.get_method_name(),
            "reasoning": "No keyword patterns matched",
        }

    def get_method_name(self) -> str:
        """Return analyzer method name for metrics."""
        return "keyword_fallback"
