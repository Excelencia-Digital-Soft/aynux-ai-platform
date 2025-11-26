"""
Keyword-Based Routing Strategy

Fast, rule-based domain routing using keyword matching.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DomainKeywords:
    """Keywords configuration for a domain."""

    domain: str
    primary_keywords: list[str]  # High-confidence keywords
    secondary_keywords: list[str] = field(default_factory=list)  # Supporting keywords
    exclusion_keywords: list[str] = field(default_factory=list)  # Keywords that exclude this domain
    patterns: list[str] = field(default_factory=list)  # Regex patterns
    priority: int = 0  # Higher priority wins on ties


@dataclass
class RoutingResult:
    """Result of routing decision."""

    domain: str
    confidence: float  # 0.0 - 1.0
    matched_keywords: list[str]
    strategy: str  # "keyword", "ai", "hybrid"


class KeywordRoutingStrategy:
    """
    Fast keyword-based routing strategy.

    Uses configurable keyword dictionaries to route messages to domains
    without requiring LLM calls. Best for clear, unambiguous messages.

    Example:
        ```python
        strategy = KeywordRoutingStrategy()

        # Configure domains
        strategy.add_domain(DomainKeywords(
            domain="ecommerce",
            primary_keywords=["producto", "precio", "comprar", "pedido"],
            secondary_keywords=["tienda", "envío", "stock"],
            patterns=[r"\\bprecio de\\b", r"\\bcuánto cuesta\\b"]
        ))

        result = strategy.route("¿Cuánto cuesta el producto X?")
        print(result.domain)  # "ecommerce"
        ```
    """

    # Default domain configurations
    DEFAULT_DOMAINS: list[DomainKeywords] = [
        DomainKeywords(
            domain="ecommerce",
            primary_keywords=[
                "producto",
                "precio",
                "comprar",
                "pedido",
                "orden",
                "factura",
                "promoción",
                "descuento",
                "oferta",
                "envío",
                "seguimiento",
                "tracking",
                "catálogo",
                "stock",
                "inventario",
                "carrito",
            ],
            secondary_keywords=[
                "tienda",
                "artículo",
                "costo",
                "pago",
                "tarjeta",
                "mercadería",
                "compra",
                "venta",
            ],
            patterns=[
                r"\bprecio de\b",
                r"\bcuánto cuesta\b",
                r"\bquiero comprar\b",
                r"\bmi pedido\b",
                r"\bdónde está mi\b",
                r"\btienen\b.*\?",
            ],
            priority=1,
        ),
        DomainKeywords(
            domain="healthcare",
            primary_keywords=[
                "cita",
                "turno",
                "médico",
                "doctor",
                "consulta",
                "paciente",
                "hospital",
                "clínica",
                "salud",
                "enfermedad",
                "síntoma",
                "tratamiento",
                "receta",
                "medicamento",
                "emergencia",
                "urgencia",
            ],
            secondary_keywords=[
                "especialista",
                "diagnóstico",
                "análisis",
                "estudio",
                "examen",
                "vacuna",
                "historia clínica",
            ],
            patterns=[
                r"\bsacar turno\b",
                r"\breservar cita\b",
                r"\bme duele\b",
                r"\btengo\b.*\bdolor\b",
                r"\bnecesito ver a\b",
            ],
            priority=2,
        ),
        DomainKeywords(
            domain="credit",
            primary_keywords=[
                "crédito",
                "préstamo",
                "cuota",
                "saldo",
                "deuda",
                "pago",
                "mora",
                "interés",
                "financiación",
                "cuenta",
                "estado de cuenta",
                "límite",
            ],
            secondary_keywords=[
                "banco",
                "financiera",
                "vencimiento",
                "cobranza",
                "tarjeta de crédito",
                "refinanciar",
            ],
            patterns=[
                r"\bcuánto debo\b",
                r"\bmi saldo\b",
                r"\bpagar la cuota\b",
                r"\bestado de cuenta\b",
                r"\blímite de crédito\b",
            ],
            exclusion_keywords=["producto", "comprar", "pedido"],
            priority=2,
        ),
        DomainKeywords(
            domain="excelencia",
            primary_keywords=[
                "excelencia",
                "sistema",
                "erp",
                "software",
                "soporte técnico",
                "configuración",
                "módulo",
                "reporte",
                "dashboard",
            ],
            secondary_keywords=[
                "funcionalidad",
                "integración",
                "api",
                "actualización",
            ],
            patterns=[
                r"\bcómo funciona\b",
                r"\bcómo usar\b",
                r"\bcómo configurar\b",
            ],
            priority=0,
        ),
    ]

    def __init__(self, default_domain: str = "ecommerce"):
        """
        Initialize keyword routing strategy.

        Args:
            default_domain: Domain to use when no match found
        """
        self.default_domain = default_domain
        self.domains: dict[str, DomainKeywords] = {}

        # Load default configurations
        for domain_config in self.DEFAULT_DOMAINS:
            self.add_domain(domain_config)

    def add_domain(self, config: DomainKeywords) -> None:
        """
        Add or update domain keyword configuration.

        Args:
            config: Domain keywords configuration
        """
        self.domains[config.domain] = config
        logger.debug(f"Added keyword config for domain: {config.domain}")

    def remove_domain(self, domain: str) -> bool:
        """
        Remove a domain configuration.

        Args:
            domain: Domain name to remove

        Returns:
            True if removed, False if not found
        """
        if domain in self.domains:
            del self.domains[domain]
            return True
        return False

    def route(self, message: str, context: dict[str, Any] | None = None) -> RoutingResult:
        """
        Route message to domain based on keywords.

        Args:
            message: User message
            context: Optional additional context

        Returns:
            Routing result with domain and confidence
        """
        message_lower = message.lower()
        scores: dict[str, tuple[float, list[str]]] = {}

        for domain, config in self.domains.items():
            score, matched = self._calculate_score(message_lower, config)
            if score > 0:
                scores[domain] = (score, matched)

        if not scores:
            return RoutingResult(
                domain=self.default_domain,
                confidence=0.0,
                matched_keywords=[],
                strategy="keyword",
            )

        # Get best match (highest score, then highest priority)
        best_domain = max(
            scores.keys(),
            key=lambda d: (scores[d][0], self.domains[d].priority),
        )

        score, matched = scores[best_domain]

        # Normalize confidence (0.0 - 1.0)
        confidence = min(score / 10.0, 1.0)

        return RoutingResult(
            domain=best_domain,
            confidence=confidence,
            matched_keywords=matched,
            strategy="keyword",
        )

    def _calculate_score(self, message: str, config: DomainKeywords) -> tuple[float, list[str]]:
        """
        Calculate matching score for a domain.

        Args:
            message: Lowercase message
            config: Domain configuration

        Returns:
            Tuple of (score, matched_keywords)
        """
        score = 0.0
        matched: list[str] = []

        # Check exclusion keywords first
        for keyword in config.exclusion_keywords:
            if keyword.lower() in message:
                return 0.0, []

        # Primary keywords (high value)
        for keyword in config.primary_keywords:
            if keyword.lower() in message:
                score += 3.0
                matched.append(keyword)

        # Secondary keywords (medium value)
        for keyword in config.secondary_keywords:
            if keyword.lower() in message:
                score += 1.0
                matched.append(keyword)

        # Pattern matching (high value)
        for pattern in config.patterns:
            try:
                if re.search(pattern, message, re.IGNORECASE):
                    score += 4.0
                    matched.append(f"pattern:{pattern[:20]}")
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")

        return score, matched

    def get_confidence_threshold(self) -> float:
        """Get minimum confidence for keyword routing to be trusted."""
        return 0.3

    def is_confident(self, result: RoutingResult) -> bool:
        """Check if result is confident enough to use without fallback."""
        return result.confidence >= self.get_confidence_threshold()
