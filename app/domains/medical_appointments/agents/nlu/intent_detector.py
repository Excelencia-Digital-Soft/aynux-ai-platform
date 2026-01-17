# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Intent detection for medical appointment conversations.
# ============================================================================
"""Medical Intent Detector.

Detects user intents in medical appointment conversations using a hybrid
approach combining pattern matching and LLM-based semantic understanding.

Supported Intents:
    - book_appointment: User wants to schedule an appointment
    - cancel_appointment: User wants to cancel an existing appointment
    - reschedule_appointment: User wants to change appointment date/time
    - view_appointments: User wants to see their appointments
    - select_specialty: User mentions a medical specialty
    - select_date: User mentions a date preference
    - select_time: User mentions a time preference
    - confirm: User confirms an action
    - reject: User rejects/cancels an action
    - human_request: User wants to talk to a human
    - greeting: User greets the bot
    - unknown: Intent could not be determined

Usage:
    detector = MedicalIntentDetector()
    result = await detector.detect("Quiero sacar un turno para cardiología")
    print(result.intent)  # "book_appointment"
    print(result.confidence)  # 0.95
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from app.integrations.llm import ModelComplexity, get_llm_for_task
from app.utils import extract_json_from_text

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Medical Appointment Intents
MEDICAL_INTENTS = frozenset({
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
    "view_appointments",
    "select_specialty",
    "select_date",
    "select_time",
    "select_provider",
    "confirm",
    "reject",
    "human_request",
    "greeting",
    "farewell",
    "info_query",
    "unknown",
})

# Confidence thresholds
CONFIDENCE_EXACT_MATCH = 0.98
CONFIDENCE_PATTERN_MATCH = 0.85
CONFIDENCE_LLM_HIGH = 0.90
CONFIDENCE_LLM_MEDIUM = 0.75
CONFIDENCE_THRESHOLD = 0.65


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MedicalIntentResult:
    """Result of medical intent detection.

    Attributes:
        intent: Detected intent key.
        confidence: Confidence score (0.0 to 1.0).
        method: Detection method used (pattern, llm, hybrid).
        entities: Extracted entities relevant to the intent.
        analysis: Additional analysis details.
    """

    intent: str
    confidence: float
    method: str = "pattern"
    entities: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "method": self.method,
            "entities": self.entities,
            "analysis": self.analysis,
        }

    @property
    def is_high_confidence(self) -> bool:
        """Check if result has high confidence."""
        return self.confidence >= CONFIDENCE_LLM_MEDIUM


# =============================================================================
# Intent Patterns
# =============================================================================

# Pattern definitions for medical appointments
INTENT_PATTERNS: dict[str, dict[str, Any]] = {
    "book_appointment": {
        "exact": {"turno", "cita", "agendar", "reservar"},
        "phrases": [
            "quiero un turno",
            "quiero sacar turno",
            "necesito un turno",
            "quiero agendar",
            "me gustaría agendar",
            "quisiera sacar turno",
            "necesito una cita",
            "quiero reservar",
            "me gustaría reservar",
            "puedo sacar turno",
            "puedo agendar",
            "agendar cita",
            "sacar turno",
            "pedir turno",
            "solicitar turno",
        ],
        "lemmas": {"turno", "cita", "agendar", "reservar", "solicitar"},
        "weight": 1.0,
    },
    "cancel_appointment": {
        "exact": set(),
        "phrases": [
            "cancelar turno",
            "cancelar cita",
            "anular turno",
            "dar de baja",
            "no voy a ir",
            "no puedo ir",
            "quiero cancelar",
        ],
        "lemmas": {"cancelar", "anular", "baja"},
        "weight": 1.0,
    },
    "reschedule_appointment": {
        "exact": set(),
        "phrases": [
            "cambiar turno",
            "reprogramar",
            "mover turno",
            "cambiar fecha",
            "cambiar horario",
            "modificar turno",
            "quiero cambiar",
            "necesito cambiar",
        ],
        "lemmas": {"reprogramar", "cambiar", "mover", "modificar", "postergar"},
        "weight": 1.0,
    },
    "view_appointments": {
        "exact": set(),
        "phrases": [
            "ver turnos",
            "mis turnos",
            "mis citas",
            "tengo turno",
            "cuando es mi turno",
            "consultar turno",
            "ver mi cita",
            "próximos turnos",
        ],
        "lemmas": {"ver", "consultar", "mostrar"},
        "weight": 0.9,
    },
    "confirm": {
        "exact": {"sí", "si", "yes", "ok", "dale", "confirmo", "correcto", "acepto", "1"},
        "phrases": [
            "está bien",
            "de acuerdo",
            "me parece bien",
            "así es",
            "exacto",
            "perfecto",
            "confirmar",
        ],
        "lemmas": {"confirmar", "aceptar", "aprobar"},
        "weight": 1.2,
    },
    "reject": {
        "exact": {"no", "nope", "cancelar", "salir", "0"},
        "phrases": [
            "no quiero",
            "no gracias",
            "mejor no",
            "no me interesa",
            "cancelar",
            "volver",
        ],
        "lemmas": {"rechazar", "negar", "declinar"},
        "weight": 1.2,
    },
    "human_request": {
        "exact": {"humano", "agente", "operador", "persona"},
        "phrases": [
            "hablar con alguien",
            "quiero hablar",
            "necesito ayuda",
            "ayuda humana",
            "transferir",
            "hablar con una persona",
            "comunicar con alguien",
        ],
        "lemmas": {"humano", "agente", "operador", "transferir"},
        "weight": 1.5,
    },
    "greeting": {
        "exact": {"hola", "buenos días", "buenas tardes", "buenas noches", "buen día"},
        "phrases": [
            "hola buen",
            "hola como",
            "hola que tal",
            "buen día",
        ],
        "lemmas": {"saludar", "hola"},
        "weight": 1.0,
    },
    "farewell": {
        "exact": {"chau", "adiós", "hasta luego", "nos vemos", "bye"},
        "phrases": [
            "hasta pronto",
            "hasta mañana",
            "nos vemos",
            "me despido",
            "gracias adios",
        ],
        "lemmas": {"chau", "adiós", "despedir"},
        "weight": 1.0,
    },
    "info_query": {
        "exact": set(),
        "phrases": [
            "qué puedes hacer",
            "que puedes hacer",
            "como funciona",
            "cómo funciona",
            "qué servicios",
            "que servicios",
            "para qué sirves",
            "para que sirves",
        ],
        "lemmas": {"información", "ayuda", "servicio"},
        "weight": 0.8,
    },
}


# =============================================================================
# Intent Detector
# =============================================================================

class MedicalIntentDetector:
    """Hybrid intent detector for medical appointments.

    Uses pattern matching for high-confidence detection and LLM
    fallback for semantic understanding of ambiguous messages.

    Config options:
        use_llm_fallback: Enable LLM fallback for low confidence.
        llm_temperature: Temperature for LLM inference.
        confidence_threshold: Minimum confidence for pattern match.
    """

    # Class-level prompt template
    _prompt_template: str | None = None
    _template_loaded: bool = False

    # LLM settings
    LLM_TEMPERATURE = 0.2
    TEMPLATE_FILE = "medical_appointments/intent_analyzer.yaml"

    def __init__(
        self,
        use_llm_fallback: bool = True,
        templates_dir: Path | str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize intent detector.

        Args:
            use_llm_fallback: Enable LLM for low-confidence cases.
            templates_dir: Path to prompt templates directory.
            config: Optional configuration dictionary.
        """
        self.use_llm_fallback = use_llm_fallback
        self._config = config or {}

        # Template loading
        if templates_dir is None:
            self._templates_dir = Path(__file__).parents[4] / "prompts" / "templates"
        else:
            self._templates_dir = Path(templates_dir)

        logger.info(
            f"MedicalIntentDetector initialized (llm_fallback={use_llm_fallback})"
        )

    async def _ensure_template_loaded(self) -> None:
        """Lazy load prompt template on first use."""
        if MedicalIntentDetector._template_loaded:
            return

        path = self._templates_dir / self.TEMPLATE_FILE
        if path.exists():
            try:
                content = await asyncio.to_thread(path.read_text, encoding="utf-8")
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    for prompt in data.get("prompts", []):
                        if prompt.get("key") == "medical.intent_analyzer.main":
                            MedicalIntentDetector._prompt_template = prompt.get(
                                "template", ""
                            )
                            break
                logger.debug("Loaded medical intent analyzer template")
            except Exception as e:
                logger.warning(f"Failed to load intent template: {e}")

        MedicalIntentDetector._template_loaded = True

    async def detect(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> MedicalIntentResult:
        """Detect intent from user message.

        Args:
            message: User message to analyze.
            context: Optional conversation context.

        Returns:
            MedicalIntentResult with detected intent and confidence.
        """
        context = context or {}
        text_lower = message.lower().strip()

        logger.debug(f"Detecting intent for: '{message[:50]}...'")

        # Priority 1: Context-aware detection
        if context_result := self._detect_from_context(text_lower, context):
            return context_result

        # Priority 2: Pattern matching
        pattern_result = self._detect_from_patterns(text_lower)

        # Priority 3: LLM fallback for low confidence
        if (
            self.use_llm_fallback
            and pattern_result.confidence < CONFIDENCE_THRESHOLD
            and pattern_result.intent not in {"confirm", "reject", "greeting"}
        ):
            logger.debug(
                f"Pattern confidence {pattern_result.confidence:.2f} < "
                f"{CONFIDENCE_THRESHOLD}, using LLM"
            )
            llm_result = await self._detect_with_llm(message, context, pattern_result)
            if llm_result.confidence > pattern_result.confidence:
                return llm_result

        return pattern_result

    def _detect_from_context(
        self,
        text_lower: str,
        context: dict[str, Any],
    ) -> MedicalIntentResult | None:
        """Detect intent based on conversation context.

        Args:
            text_lower: Lowercase message text.
            context: Conversation context.

        Returns:
            MedicalIntentResult or None if no context match.
        """
        # Awaiting confirmation
        if context.get("awaiting_confirmation"):
            if self._is_confirmation(text_lower):
                return MedicalIntentResult(
                    intent="confirm",
                    confidence=CONFIDENCE_EXACT_MATCH,
                    method="context_confirmation",
                    analysis={"matched": text_lower, "context": "awaiting_confirmation"},
                )
            if self._is_rejection(text_lower):
                return MedicalIntentResult(
                    intent="reject",
                    confidence=CONFIDENCE_EXACT_MATCH,
                    method="context_rejection",
                    analysis={"matched": text_lower, "context": "awaiting_confirmation"},
                )

        # Awaiting selection (numeric input)
        if context.get("awaiting_selection"):
            if text_lower.isdigit():
                return MedicalIntentResult(
                    intent="select_option",
                    confidence=CONFIDENCE_EXACT_MATCH,
                    method="context_selection",
                    entities={"selection": int(text_lower)},
                    analysis={"context": "awaiting_selection"},
                )

        # Awaiting document input (DNI)
        if context.get("awaiting_document"):
            dni_match = re.search(r"\d{7,8}", text_lower)
            if dni_match:
                return MedicalIntentResult(
                    intent="provide_document",
                    confidence=CONFIDENCE_EXACT_MATCH,
                    method="context_document",
                    entities={"document": dni_match.group()},
                    analysis={"context": "awaiting_document"},
                )

        return None

    def _detect_from_patterns(self, text_lower: str) -> MedicalIntentResult:
        """Detect intent using pattern matching.

        Args:
            text_lower: Lowercase message text.

        Returns:
            MedicalIntentResult with pattern-based detection.
        """
        scores: dict[str, float] = {}

        for intent, patterns in INTENT_PATTERNS.items():
            score = self._calculate_pattern_score(text_lower, patterns)
            scores[intent] = score

        # Get best match
        if scores:
            best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
            best_score = scores[best_intent]
        else:
            best_intent = "unknown"
            best_score = 0.0

        return MedicalIntentResult(
            intent=best_intent if best_score > 0.3 else "unknown",
            confidence=min(best_score, CONFIDENCE_PATTERN_MATCH),
            method="pattern",
            analysis={"scores": scores},
        )

    def _calculate_pattern_score(
        self,
        text_lower: str,
        patterns: dict[str, Any],
    ) -> float:
        """Calculate score for a single intent pattern.

        Args:
            text_lower: Lowercase message text.
            patterns: Pattern dictionary for the intent.

        Returns:
            Score between 0.0 and 1.0.
        """
        score = 0.0
        weight = patterns.get("weight", 1.0)

        # Exact match
        exact_patterns = patterns.get("exact", set())
        if text_lower in exact_patterns:
            return 0.98 * weight

        # Phrase matching
        phrases = patterns.get("phrases", [])
        for phrase in phrases:
            if phrase in text_lower:
                score = max(score, 0.8)
                if text_lower.startswith(phrase):
                    score = max(score, 0.9)

        # Lemma/keyword matching
        lemmas = patterns.get("lemmas", set())
        words = set(text_lower.split())
        lemma_matches = words & lemmas
        if lemma_matches:
            score = max(score, 0.4 + (len(lemma_matches) * 0.15))

        return min(score * weight, 1.0)

    async def _detect_with_llm(
        self,
        message: str,
        context: dict[str, Any],
        pattern_result: MedicalIntentResult,
    ) -> MedicalIntentResult:
        """Detect intent using LLM fallback.

        Args:
            message: Original user message.
            context: Conversation context.
            pattern_result: Result from pattern matching.

        Returns:
            MedicalIntentResult from LLM analysis.
        """
        try:
            await self._ensure_template_loaded()
            prompt = self._build_llm_prompt(message, context)

            llm = get_llm_for_task(
                complexity=ModelComplexity.SIMPLE,
                temperature=self.LLM_TEMPERATURE,
            )
            response = await llm.ainvoke(prompt)
            response_text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )

            return self._parse_llm_response(response_text, pattern_result)

        except Exception as e:
            logger.error(f"LLM intent detection failed: {e}", exc_info=True)
            pattern_result.analysis["llm_error"] = str(e)
            return pattern_result

    def _build_llm_prompt(
        self,
        message: str,
        context: dict[str, Any],
    ) -> str:
        """Build prompt for LLM intent detection.

        Args:
            message: User message.
            context: Conversation context.

        Returns:
            Formatted prompt string.
        """
        if MedicalIntentDetector._prompt_template:
            return MedicalIntentDetector._prompt_template.format(
                message=message,
                intents=", ".join(MEDICAL_INTENTS),
                context=context,
            )

        # Default prompt if template not loaded
        return f"""Analiza el siguiente mensaje y determina la intención del usuario
en el contexto de agendar turnos médicos.

Mensaje: "{message}"

Intenciones posibles:
- book_appointment: Quiere agendar un turno
- cancel_appointment: Quiere cancelar un turno
- reschedule_appointment: Quiere cambiar fecha/hora de turno
- view_appointments: Quiere ver sus turnos
- confirm: Confirma una acción
- reject: Rechaza o cancela
- human_request: Quiere hablar con un humano
- greeting: Saludo
- unknown: No se puede determinar

Responde SOLO con JSON:
{{"intent": "nombre_intent", "confidence": 0.0-1.0, "entities": {{}}}}"""

    def _parse_llm_response(
        self,
        response_text: str,
        fallback: MedicalIntentResult,
    ) -> MedicalIntentResult:
        """Parse LLM response into MedicalIntentResult.

        Args:
            response_text: Raw LLM response.
            fallback: Fallback result if parsing fails.

        Returns:
            MedicalIntentResult from LLM or fallback.
        """
        try:
            default = {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": {},
            }

            extracted = extract_json_from_text(
                response_text,
                default=default,
                required_keys=["intent"],
            )

            if not extracted or not isinstance(extracted, dict):
                return fallback

            intent = extracted.get("intent", "unknown")

            # Validate intent
            if intent not in MEDICAL_INTENTS:
                intent = "unknown"

            confidence = min(float(extracted.get("confidence", 0.0)), 1.0)
            entities = extracted.get("entities", {})

            if not isinstance(entities, dict):
                entities = {}

            return MedicalIntentResult(
                intent=intent,
                confidence=confidence,
                method="llm",
                entities=entities,
                analysis={"raw_response": response_text[:200]},
            )

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return fallback

    def _is_confirmation(self, text: str) -> bool:
        """Check if text is a confirmation."""
        confirm_patterns = INTENT_PATTERNS.get("confirm", {})
        exact = confirm_patterns.get("exact", set())
        phrases = confirm_patterns.get("phrases", [])

        if text in exact:
            return True
        return any(phrase in text for phrase in phrases)

    def _is_rejection(self, text: str) -> bool:
        """Check if text is a rejection."""
        reject_patterns = INTENT_PATTERNS.get("reject", {})
        exact = reject_patterns.get("exact", set())
        phrases = reject_patterns.get("phrases", [])

        if text in exact:
            return True
        return any(phrase in text for phrase in phrases)


# =============================================================================
# Factory Function
# =============================================================================

def get_medical_intent_detector(
    use_llm_fallback: bool = True,
    config: dict[str, Any] | None = None,
) -> MedicalIntentDetector:
    """Factory function to create MedicalIntentDetector.

    Args:
        use_llm_fallback: Enable LLM fallback.
        config: Optional configuration.

    Returns:
        Configured MedicalIntentDetector instance.
    """
    return MedicalIntentDetector(
        use_llm_fallback=use_llm_fallback,
        config=config,
    )
