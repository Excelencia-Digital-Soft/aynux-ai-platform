"""
Pharmacy Intent Analyzer

Hybrid intent detection for pharmacy domain using:
1. spaCy NLU for fast entity extraction and linguistic analysis
2. LLM (SIMPLE tier) for semantic understanding when needed
3. PromptManager for externalized, configurable prompts
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import spacy
from spacy.language import Language

from app.integrations.llm import ModelComplexity, get_llm_for_task
from app.prompts.manager import PromptManager
from app.utils import extract_json_from_text

logger = logging.getLogger(__name__)


@dataclass
class PharmacyIntentResult:
    """Result of pharmacy intent analysis."""

    intent: str
    confidence: float
    is_out_of_scope: bool = False
    suggested_response: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    method: str = "hybrid"
    analysis: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PharmacyIntentResult:
        """Create instance from dictionary."""
        return cls(
            intent=data.get("intent", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            is_out_of_scope=bool(data.get("is_out_of_scope", False)),
            suggested_response=data.get("suggested_response"),
            entities=data.get("entities", {}),
            method=data.get("method", "hybrid"),
            analysis=data.get("analysis", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "is_out_of_scope": self.is_out_of_scope,
            "suggested_response": self.suggested_response,
            "entities": self.entities,
            "method": self.method,
            "analysis": self.analysis,
        }


# Confidence thresholds (single source of truth)
CONFIDENCE_THRESHOLD = 0.6  # LLM fallback threshold
CONFIDENCE_OUT_OF_SCOPE = 0.3
CONFIDENCE_MAX_SPACY = 0.95
CONFIDENCE_EXACT_MATCH = 0.95
CONFIDENCE_CONTAINS = 0.85

# Confirmation/rejection patterns (single source of truth - replaces 3 duplicated definitions)
CONFIRMATION_PATTERNS: dict[str, dict[str, set[str]]] = {
    "confirm": {
        "exact": {"si", "sí", "ok", "dale", "bueno", "listo", "claro", "perfecto", "bien"},
        "contains": {"confirmo", "acepto", "de acuerdo", "correcto", "afirmativo"},
    },
    "reject": {
        "exact": {"no"},
        "contains": {"cancelar", "rechazar", "incorrecto", "salir", "anular", "no quiero", "negar"},
    },
}

# Keyword patterns for fallback (when spaCy unavailable)
KEYWORD_PATTERNS: dict[str, list[str]] = {
    "debt_query": ["deuda", "saldo", "debo", "cuenta", "pendiente"],
    "invoice": ["factura", "recibo", "pagar", "pago", "comprobante"],
    "greeting": ["hola", "buenos días", "buenas tardes", "buenas noches", "buenas"],
}

# Greeting patterns for priority detection (exact match or prefix)
GREETING_EXACT: frozenset[str] = frozenset(
    {
        "hola",
        "hey",
        "buenas",
        "buenos dias",
        "buen dia",
        "buen día",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "que tal",
        "qué tal",
        "como estas",
        "cómo estás",
        "hi",
        "hello",
    }
)
GREETING_PREFIXES: tuple[str, ...] = ("hola ", "buenas ", "buenos ", "hey ", "saludos ")


class PharmacyIntentAnalyzer:
    """
    Hybrid intent analyzer for pharmacy domain.

    Uses multi-layer approach:
    1. spaCy for fast linguistic analysis (~50-100ms)
    2. LLM fallback for ambiguous cases
    3. PromptManager for externalized prompts
    """

    _nlp_model: Language | None = None
    _instance: PharmacyIntentAnalyzer | None = None

    VALID_INTENTS = frozenset(
        {"debt_query", "confirm", "reject", "invoice", "register", "greeting", "summary", "data_query", "unknown"}
    )

    PHARMACY_CAPABILITIES = [
        "consultar deuda/saldo pendiente",
        "confirmar deuda para pago",
        "generar recibo/factura",
        "registrarse como cliente nuevo",
    ]

    # Intent patterns for spaCy analysis
    INTENT_PATTERNS = {
        "debt_query": {
            "lemmas": {"deuda", "deber", "saldo", "cuenta", "pendiente", "consultar", "estado"},
            "phrases": ["cuánto debo", "cuanto debo", "mi deuda", "mi saldo", "estado de cuenta"],
            "weight": 1.0,
        },
        "confirm": {
            "lemmas": {"confirmar", "aceptar", "acordar"},
            "phrases": [],
            "weight": 1.0,
            "exact_match": True,
        },  # Use CONFIRMATION_PATTERNS
        "reject": {
            "lemmas": {"cancelar", "rechazar", "anular", "salir"},
            "phrases": [],
            "weight": 1.0,
            "exact_match": True,
        },  # Use CONFIRMATION_PATTERNS
        "invoice": {
            "lemmas": {"factura", "recibo", "comprobante", "pagar", "pago", "facturar"},
            "phrases": ["generar factura", "quiero pagar", "mi factura", "generar recibo"],
            "weight": 1.0,
        },
        "register": {
            "lemmas": {"registrar", "inscribir", "nuevo"},
            "phrases": ["soy nuevo", "registrarme", "nuevo cliente", "crear cuenta"],
            "weight": 0.9,
        },
        "greeting": {
            "lemmas": {"hola", "saludar", "saludo", "buenas", "buenos"},
            "phrases": ["hola", "buenos días", "buenas tardes", "buenas noches", "buen día", "hey", "buenas"],
            "weight": 1.0,  # Same priority as other intents
        },
        "summary": {
            "lemmas": {"resumen", "resumir", "detalle", "detallar"},
            "phrases": ["resumen de", "detalle de", "dame un resumen"],
            "weight": 0.9,
        },
        "data_query": {
            "lemmas": {
                "medicamento",
                "producto",
                "consumir",
                "gastar",
                "comprar",
                "caro",
                "barato",
                "mayor",
                "menor",
                "más",
                "menos",
                "compra",
                "valor",
                "importe",
                "factura",
                "análisis",
            },
            "phrases": [
                # Preguntas sobre medicamentos/productos
                "que medicamento",
                "cual medicamento",
                "cuál medicamento",
                "que producto",
                "cual producto",
                "cuál producto",
                "mis medicamentos",
                "mis productos",
                # Preguntas sobre gastos/compras
                "cuanto gaste",
                "cuánto gasté",
                "que compre",
                "qué compré",
                "que he comprado",
                "que he gastado",
                "analizar mis",
                # Preguntas sobre valores/importes
                "el más caro",
                "el mas caro",
                "el más barato",
                "debo más",
                "debo mas",
                "mayor deuda",
                "mayor importe",
                "compras de mayor valor",
                "producto de mayor",
                "medicamento que más",
                "mayor valor",
                # Preguntas sobre cantidades
                "cuantos productos",
                "cuántos productos",
                "cuantos medicamentos",
                "cuántos medicamentos",
            ],
            "weight": 1.2,  # Prioridad sobre debt_query cuando hay overlap
        },
    }

    LLM_TEMPERATURE = 0.2

    def __new__(cls, *args: Any, **kwargs: Any) -> PharmacyIntentAnalyzer:
        """Singleton pattern for shared resources."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        prompt_manager: PromptManager | None = None,
        use_llm_fallback: bool = True,
        model_name: str = "es_core_news_sm",
    ):
        """Initialize pharmacy intent analyzer."""
        if getattr(self, "_initialized", False):
            return
        self._prompt_manager = prompt_manager
        self.use_llm_fallback = use_llm_fallback
        self.model_name = model_name
        self._load_spacy_model()
        self._initialized = True
        logger.info("PharmacyIntentAnalyzer initialized")

    @property
    def prompt_manager(self) -> PromptManager:
        """Get or create PromptManager instance."""
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager()
        return self._prompt_manager

    @property
    def nlp(self) -> Language | None:
        """Get shared spaCy model."""
        return PharmacyIntentAnalyzer._nlp_model

    def _load_spacy_model(self) -> None:
        """Load spaCy model (shared across instances)."""
        if PharmacyIntentAnalyzer._nlp_model is not None:
            return
        try:
            PharmacyIntentAnalyzer._nlp_model = spacy.load(self.model_name)
            logger.info(f"spaCy model '{self.model_name}' loaded")
        except OSError:
            logger.warning(f"spaCy model '{self.model_name}' not found, using blank")
            PharmacyIntentAnalyzer._nlp_model = spacy.blank("es")

    async def analyze(self, message: str, context: dict[str, Any] | None = None) -> PharmacyIntentResult:
        """Analyze user message and detect pharmacy intent using hybrid approach."""
        context = context or {}
        logger.info(f"Analyzing pharmacy intent: '{message[:50]}...'")

        spacy_result = self._analyze_with_spacy(message, context)

        # LLM fallback for low confidence (except reliable intents)
        if (
            self.use_llm_fallback
            and spacy_result.confidence < CONFIDENCE_THRESHOLD
            and spacy_result.intent not in {"confirm", "reject", "greeting"}
        ):
            logger.debug(f"spaCy confidence {spacy_result.confidence:.2f} < {CONFIDENCE_THRESHOLD}, using LLM")
            llm_result = await self._analyze_with_llm(message, context, spacy_result)
            if llm_result.confidence > spacy_result.confidence:
                llm_result.analysis["spacy_result"] = spacy_result.to_dict()
                return llm_result

        return spacy_result

    def _analyze_with_spacy(self, message: str, context: dict[str, Any]) -> PharmacyIntentResult:
        """Analyze message using spaCy NLU."""
        if self.nlp is None:
            return self._keyword_fallback(message, context)

        text_lower = message.lower().strip()
        doc = self.nlp(text_lower)

        # Priority 1: Check confirmation context first
        if context.get("awaiting_confirmation"):
            if result := self._match_confirmation(text_lower):
                return result

        # Priority 2: Detect greeting with high confidence (before general scoring)
        if result := self._match_greeting_priority(text_lower):
            return result

        lemmas = {token.lemma_.lower() for token in doc if not token.is_stop and not token.is_punct}
        scores = {
            intent: self._calculate_intent_score(text_lower, lemmas, patterns, doc)
            for intent, patterns in self.INTENT_PATTERNS.items()
        }

        best_intent, best_score = max(scores.items(), key=lambda x: x[1])
        is_out_of_scope = best_score < CONFIDENCE_OUT_OF_SCOPE

        return PharmacyIntentResult(
            intent=best_intent if not is_out_of_scope else "unknown",
            confidence=min(best_score, CONFIDENCE_MAX_SPACY),
            is_out_of_scope=is_out_of_scope,
            entities=self._extract_entities(doc, text_lower),
            method="spacy",
            analysis={"lemmas": list(lemmas), "scores": scores, "token_count": len(doc)},
        )

    def _match_confirmation(self, text_lower: str) -> PharmacyIntentResult | None:
        """Match confirmation/rejection patterns using unified logic."""
        for intent, patterns in CONFIRMATION_PATTERNS.items():
            if text_lower in patterns["exact"]:
                return self._create_match_result(intent, CONFIDENCE_EXACT_MATCH, "exact", text_lower)
            for pattern in patterns["contains"]:
                if pattern in text_lower:
                    return self._create_match_result(intent, CONFIDENCE_CONTAINS, "contains", pattern)
        return None

    def _match_greeting_priority(self, text_lower: str) -> PharmacyIntentResult | None:
        """
        Match greeting patterns with high priority.

        This runs BEFORE general intent scoring to ensure greetings are
        always detected reliably, even for short messages like "hola".
        """
        # Exact match (highest confidence)
        if text_lower in GREETING_EXACT:
            return PharmacyIntentResult(
                intent="greeting",
                confidence=CONFIDENCE_EXACT_MATCH,
                is_out_of_scope=False,
                entities={},
                method="greeting_priority",
                analysis={"matched_pattern": text_lower, "match_type": "exact"},
            )

        # Prefix match (high confidence)
        for prefix in GREETING_PREFIXES:
            if text_lower.startswith(prefix):
                return PharmacyIntentResult(
                    intent="greeting",
                    confidence=CONFIDENCE_CONTAINS,
                    is_out_of_scope=False,
                    entities={},
                    method="greeting_priority",
                    analysis={"matched_pattern": prefix, "match_type": "prefix"},
                )

        return None

    def _create_match_result(
        self, intent: str, confidence: float, match_type: str, pattern: str
    ) -> PharmacyIntentResult:
        """Factory for pattern match results."""
        return PharmacyIntentResult(
            intent=intent,
            confidence=confidence,
            is_out_of_scope=False,
            entities={},
            method="pattern_match",
            analysis={"matched_pattern": pattern, "match_type": match_type},
        )

    def _calculate_intent_score(self, text_lower: str, lemmas: set[str], patterns: dict[str, Any], doc: Any) -> float:
        """Calculate score for a single intent based on patterns."""
        score = 0.0
        weight = patterns.get("weight", 1.0)
        exact_match = patterns.get("exact_match", False)

        # Lemma matching
        intent_lemmas = patterns.get("lemmas", set())
        if lemma_matches := lemmas & intent_lemmas:
            score += len(lemma_matches) * 0.4

        # Phrase matching
        for phrase in patterns.get("phrases", []):
            if exact_match:
                if text_lower == phrase or text_lower.startswith(f"{phrase} "):
                    score += 0.9
                    break
            elif phrase in text_lower:
                score += 0.5

        return min(score * weight, 1.0)

    def _extract_entities(self, doc: Any, text_lower: str) -> dict[str, Any]:
        """Extract pharmacy-relevant entities from message."""
        entities: dict[str, Any] = {"amount": None, "date": None, "document_number": None}

        # Amount extraction
        amount_pattern = r"\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d+)?)"
        if amount_matches := re.findall(amount_pattern, text_lower):
            try:
                entities["amount"] = float(amount_matches[0].replace(".", "").replace(",", "."))
            except ValueError:
                pass

        # DNI extraction
        if dni_matches := re.findall(r"\b(\d{7,8})\b", text_lower):
            entities["document_number"] = dni_matches[0]

        # spaCy NER
        for ent in doc.ents:
            if ent.label_ == "MONEY" and entities["amount"] is None:
                try:
                    entities["amount"] = float(re.sub(r"[^\d.]", "", ent.text))
                except ValueError:
                    pass
            elif ent.label_ in ("DATE", "TIME"):
                entities["date"] = ent.text

        return entities

    def _keyword_fallback(self, message: str, context: dict[str, Any]) -> PharmacyIntentResult:
        """Keyword fallback when spaCy unavailable."""
        text_lower = message.lower().strip()

        if context.get("awaiting_confirmation"):
            if result := self._match_confirmation(text_lower):
                return result

        for intent, keywords in KEYWORD_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                return PharmacyIntentResult(intent=intent, confidence=0.7, method="keyword_fallback")

        return PharmacyIntentResult(intent="unknown", confidence=0.3, is_out_of_scope=True, method="keyword_fallback")

    async def _analyze_with_llm(
        self, message: str, context: dict[str, Any], spacy_result: PharmacyIntentResult
    ) -> PharmacyIntentResult:
        """Fallback to LLM for semantic understanding."""
        try:
            prompt = await self._build_llm_prompt(message, context)
            llm = get_llm_for_task(complexity=ModelComplexity.SIMPLE, temperature=self.LLM_TEMPERATURE)
            response = await llm.ainvoke(prompt)
            response_text = response.content if isinstance(response.content, str) else str(response.content)
            return self._parse_llm_response(response_text, spacy_result)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}", exc_info=True)
            spacy_result.analysis["llm_error"] = str(e)
            return spacy_result

    async def _build_llm_prompt(self, message: str, context: dict[str, Any]) -> str:
        """Build prompt using PromptManager."""
        # Format conversation history or indicate none
        conversation_history = context.get("conversation_history", "")
        if not conversation_history:
            conversation_history = "(Sin historial previo - primer mensaje)"

        return await self.prompt_manager.get_prompt(
            "pharmacy.intent_analyzer.main",
            variables={
                "message": message,
                "customer_identified": context.get("customer_identified", False),
                "awaiting_confirmation": context.get("awaiting_confirmation", False),
                "debt_status": context.get("debt_status", "none"),
                "capabilities": "\n".join(f"- {cap}" for cap in self.PHARMACY_CAPABILITIES),
                "conversation_history": conversation_history,
            },
        )

    def _parse_llm_response(self, response_text: str, spacy_result: PharmacyIntentResult) -> PharmacyIntentResult:
        """Parse LLM response into PharmacyIntentResult."""
        try:
            default = {
                "intent": "unknown",
                "confidence": 0.0,
                "is_out_of_scope": False,
                "suggested_response": None,
                "entities": spacy_result.entities,
            }

            extracted = extract_json_from_text(response_text, default=default, required_keys=["intent"])
            if not extracted or not isinstance(extracted, dict):
                return spacy_result

            intent = extracted.get("intent", "unknown")
            if intent not in self.VALID_INTENTS:
                intent = "unknown"

            merged_entities = {**extracted.get("entities", {}), **spacy_result.entities}

            return PharmacyIntentResult(
                intent=intent,
                confidence=min(float(extracted.get("confidence", 0.0)), 1.0),
                is_out_of_scope=bool(extracted.get("is_out_of_scope", False)),
                suggested_response=extracted.get("suggested_response"),
                entities=merged_entities,
                method="llm",
                analysis={"raw_response": response_text[:200]},
            )
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return spacy_result

    def is_available(self) -> bool:
        """Check if analyzer is properly initialized."""
        return self.nlp is not None

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded models."""
        return {
            "spacy_available": self.nlp is not None,
            "spacy_model": self.model_name,
            "llm_fallback_enabled": self.use_llm_fallback,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "valid_intents": list(self.VALID_INTENTS),
        }
