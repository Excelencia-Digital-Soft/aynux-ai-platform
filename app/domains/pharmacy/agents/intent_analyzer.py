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
from typing import Any

import spacy
from spacy.language import Language

from app.domains.pharmacy.agents.entity_extractor import PharmacyEntityExtractor
from app.domains.pharmacy.agents.intent_patterns import (
    CONFIDENCE_EXACT_MATCH,
    CONFIDENCE_MAX_SPACY,
    CONFIDENCE_OUT_OF_SCOPE,
    CONFIDENCE_THRESHOLD,
    INTENT_PATTERNS,
    KEYWORD_PATTERNS,
    PHARMACY_CAPABILITIES,
    VALID_INTENTS,
)
from app.domains.pharmacy.agents.intent_result import PharmacyIntentResult
from app.domains.pharmacy.agents.pattern_matchers import (
    is_payment_intent,
    match_confirmation,
    match_greeting,
)
from app.integrations.llm import ModelComplexity, get_llm_for_task
from app.prompts.manager import PromptManager
from app.utils import extract_json_from_text

logger = logging.getLogger(__name__)


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
        self._entity_extractor = PharmacyEntityExtractor()
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
            if result := match_confirmation(text_lower):
                return result

        # Priority 2: Check document input context - detect DNI when awaiting document
        if context.get("awaiting_document_input"):
            dni_match = re.search(r'\d{7,8}', text_lower)
            if dni_match:
                return PharmacyIntentResult(
                    intent="document_input",
                    confidence=CONFIDENCE_EXACT_MATCH,
                    is_out_of_scope=False,
                    entities={"dni": dni_match.group()},
                    method="awaiting_document_detection",
                    analysis={"detected": "dni_while_awaiting"},
                )

        # Priority 3: Detect greeting with high confidence
        if result := match_greeting(text_lower):
            return result

        # Extract entities early for payment detection
        entities = self._entity_extractor.extract(doc, text_lower)

        # Priority 3: Detect capability/info questions (que puedes hacer, etc.)
        # These must be caught BEFORE payment detection to avoid LLM misclassification
        if self._is_capability_question(text_lower):
            return PharmacyIntentResult(
                intent="info_query",
                confidence=CONFIDENCE_EXACT_MATCH,
                is_out_of_scope=False,
                entities=entities,
                method="capability_detection",
                analysis={"detected": "capability_question"},
            )

        # Priority 4: Detect payment intent (pagar + cantidad)
        if is_payment_intent(text_lower, entities):
            return PharmacyIntentResult(
                intent="invoice",
                confidence=CONFIDENCE_EXACT_MATCH,
                is_out_of_scope=False,
                entities=entities,
                method="payment_detection",
                analysis={"detected": "payment_with_amount"},
            )

        # Score all intents
        lemmas = {token.lemma_.lower() for token in doc if not token.is_stop and not token.is_punct}
        scores = {
            intent: self._calculate_intent_score(text_lower, lemmas, patterns, doc)
            for intent, patterns in INTENT_PATTERNS.items()
        }

        best_intent, best_score = max(scores.items(), key=lambda x: x[1])
        is_out_of_scope = best_score < CONFIDENCE_OUT_OF_SCOPE

        return PharmacyIntentResult(
            intent=best_intent if not is_out_of_scope else "unknown",
            confidence=min(best_score, CONFIDENCE_MAX_SPACY),
            is_out_of_scope=is_out_of_scope,
            entities=entities,
            method="spacy",
            analysis={"lemmas": list(lemmas), "scores": scores, "token_count": len(doc)},
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

    def _is_capability_question(self, text: str) -> bool:
        """Check if message is asking about bot capabilities.

        These phrases indicate the user is asking what the bot can do,
        not requesting a specific action like payment.
        """
        capability_phrases = (
            # Direct capability questions
            "que puedes hacer",
            "qué puedes hacer",
            "que puedes",
            "qué puedes",
            "puedes hacer",
            "que haces",
            "qué haces",
            "que sabes",
            "qué sabes",
            "que sabes hacer",
            "qué sabes hacer",
            # Purpose questions
            "para que sirves",
            "para qué sirves",
            "para que eres",
            "para qué eres",
            # Service questions
            "que servicios",
            "qué servicios",
            "que ofreces",
            "qué ofreces",
            "servicios ofreces",
            # Help questions
            "en que me ayudas",
            "en qué me ayudas",
            "como me ayudas",
            "cómo me ayudas",
            "que me ofreces",
            "qué me ofreces",
            # Function questions
            "como funciona",
            "cómo funciona",
            "como funcionas",
            "cómo funcionas",
            # More capability
            "que mas puedes",
            "qué más puedes",
            "que mas haces",
            "qué más haces",
        )
        return any(phrase in text for phrase in capability_phrases)

    def _keyword_fallback(self, message: str, context: dict[str, Any]) -> PharmacyIntentResult:
        """Keyword fallback when spaCy unavailable."""
        text_lower = message.lower().strip()

        if context.get("awaiting_confirmation"):
            if result := match_confirmation(text_lower):
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
        conversation_history = context.get("conversation_history", "")
        if not conversation_history:
            conversation_history = "(Sin historial previo - primer mensaje)"

        return await self.prompt_manager.get_prompt(
            "pharmacy.intent_analyzer.main",
            variables={
                "message": message,
                "customer_identified": context.get("customer_identified", False),
                "awaiting_confirmation": context.get("awaiting_confirmation", False),
                "awaiting_document_input": context.get("awaiting_document_input", False),
                "debt_status": context.get("debt_status", "none"),
                "capabilities": "\n".join(f"- {cap}" for cap in PHARMACY_CAPABILITIES),
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
            if intent not in VALID_INTENTS:
                intent = "unknown"

            # Ensure entities is a dict before merging (LLM may return malformed response)
            llm_entities = extracted.get("entities", {})
            if not isinstance(llm_entities, dict):
                llm_entities = {}
            merged_entities = {**llm_entities, **spacy_result.entities}

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
            "valid_intents": list(VALID_INTENTS),
        }
