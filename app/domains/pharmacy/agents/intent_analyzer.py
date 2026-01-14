"""
Pharmacy Intent Analyzer

Database-driven hybrid intent detection for pharmacy domain using:
1. Configurable patterns from database (cached per-organization)
2. spaCy NLU for fast entity extraction and linguistic analysis
3. LLM (SIMPLE tier) for semantic understanding when needed
4. YAML templates loaded directly for LLM prompts

IMPORTANT: No fallback to hardcoded patterns. Patterns must be in database.

Usage patterns:
1. Multi-tenant (recommended): Pass db/organization_id in analyze() method
   analyzer = PharmacyIntentAnalyzer()
   result = await analyzer.analyze(message, context, db=session, organization_id=org_id)

2. Single-tenant: Pass db/organization_id at construction
   analyzer = PharmacyIntentAnalyzer(db=session, organization_id=org_id)
   result = await analyzer.analyze(message, context)
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import spacy
import yaml
from spacy.language import Language

# Use domain_intent_cache for multi-domain support (replaces intent_pattern_cache)
from app.core.cache.domain_intent_cache import domain_intent_cache
from app.domains.pharmacy.agents.entity_extractor import PharmacyEntityExtractor
from app.domains.pharmacy.agents.intent_patterns import (
    CONFIDENCE_CONTAINS,
    CONFIDENCE_EXACT_MATCH,
    CONFIDENCE_MAX_SPACY,
    CONFIDENCE_OUT_OF_SCOPE,
    CONFIDENCE_THRESHOLD,
    PHARMACY_CAPABILITIES,
)
from app.domains.pharmacy.agents.intent_result import PharmacyIntentResult
from app.domains.pharmacy.agents.pattern_matchers import is_payment_intent_from_patterns
from app.integrations.llm import ModelComplexity, get_llm_for_task
from app.utils import extract_json_from_text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PharmacyIntentAnalyzer:
    """
    Database-driven intent analyzer for pharmacy domain.

    Uses multi-layer approach:
    1. Patterns loaded from database (cached per-organization)
    2. spaCy for fast linguistic analysis (~50-100ms)
    3. LLM fallback for ambiguous cases
    4. YAML templates loaded directly for LLM prompts

    IMPORTANT: No fallback to hardcoded patterns. If patterns are not in
    database, intent detection will return "unknown".

    Supports two usage patterns:
    - Multi-tenant: Pass db/organization_id in analyze() call (recommended)
    - Single-tenant: Pass db/organization_id at construction time
    """

    _nlp_model: Language | None = None

    LLM_TEMPERATURE = 0.2

    # YAML template path (relative to prompts/templates)
    TEMPLATE_FILE = "pharmacy/core/intent_analyzer.yaml"

    # Cache patterns per organization to avoid reloading across calls
    _patterns_cache: dict[UUID, dict[str, Any]] = {}

    def __init__(
        self,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
        templates_dir: Path | str | None = None,
        use_llm_fallback: bool = True,
        model_name: str = "es_core_news_sm",
    ):
        """Initialize pharmacy intent analyzer.

        Args:
            db: Optional AsyncSession for database access (can be passed in analyze())
            organization_id: Optional tenant UUID for loading patterns (can be passed in analyze())
            templates_dir: Path to prompts/templates directory
            use_llm_fallback: Enable LLM fallback for low confidence
            model_name: spaCy model to use
        """
        self._db = db
        self._organization_id = organization_id
        self.use_llm_fallback = use_llm_fallback
        self.model_name = model_name
        self._entity_extractor = PharmacyEntityExtractor()
        self._patterns: dict[str, Any] | None = None
        self._current_org_id: UUID | None = None

        # Template loading
        if templates_dir is None:
            self._templates_dir = Path(__file__).parents[3] / "prompts" / "templates"
        else:
            self._templates_dir = Path(templates_dir)
        self._prompt_templates: dict[str, str] = {}
        self._templates_loaded = False

        self._load_spacy_model()
        if organization_id:
            logger.info(f"PharmacyIntentAnalyzer initialized for org {organization_id}")
        else:
            logger.info("PharmacyIntentAnalyzer initialized (multi-tenant mode)")

    async def _ensure_templates_loaded(self) -> None:
        """Lazy load YAML templates on first use."""
        if self._templates_loaded:
            return

        path = self._templates_dir / self.TEMPLATE_FILE
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                logger.warning("Invalid intent analyzer template format, expected dict")
                self._templates_loaded = True
                return
            for prompt in data.get("prompts", []):
                key = prompt.get("key", "")
                template = prompt.get("template", "")
                if key and template:
                    self._prompt_templates[key] = template
            logger.debug(f"Loaded {len(self._prompt_templates)} intent analyzer templates")
        except Exception as e:
            logger.warning(f"Failed to load intent analyzer templates: {e}")

        self._templates_loaded = True

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

    async def _ensure_patterns_loaded(
        self,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> None:
        """Ensure patterns are loaded from cache/database.

        Args:
            db: Optional AsyncSession (uses self._db if not provided)
            organization_id: Optional organization UUID (uses self._organization_id if not provided)

        Note:
            If no db session is available, the cache will create its own session.
            This enables lazy initialization for multi-tenant scenarios.
        """
        # Resolve org_id from parameters or instance attributes
        org_id = organization_id or self._organization_id

        # Check if we need to load patterns (different org or first load)
        if self._patterns is not None and self._current_org_id == org_id:
            return  # Patterns already loaded for this org

        if org_id is None:
            logger.warning("Cannot load patterns: organization_id not provided")
            self._patterns = {}
            return

        # Resolve db session - cache can create its own if None
        # This enables lazy initialization without requiring db at construction
        resolved_db = db or self._db

        # Load patterns from cache (db can be None - cache will create own session)
        # Domain is always "pharmacy" for this analyzer
        self._patterns = await domain_intent_cache.get_patterns(resolved_db, org_id, "pharmacy")
        self._current_org_id = org_id

        if not self._patterns.get("intents"):
            logger.warning(f"No intent patterns found in database for org {org_id}")

    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        *,
        db: "AsyncSession | None" = None,
        organization_id: UUID | None = None,
    ) -> PharmacyIntentResult:
        """Analyze user message and detect pharmacy intent using hybrid approach.

        Args:
            message: User message to analyze
            context: Optional context dict with conversation state
            db: Optional AsyncSession (uses self._db if not provided)
            organization_id: Optional org UUID (uses self._organization_id if not provided)

        Returns:
            PharmacyIntentResult with detected intent and confidence
        """
        context = context or {}

        # Load patterns from cache/database
        await self._ensure_patterns_loaded(db, organization_id)

        logger.info(f"Analyzing pharmacy intent: '{message[:50]}...'")

        spacy_result = await self._analyze_with_spacy(message, context)

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

    async def _analyze_with_spacy(self, message: str, context: dict[str, Any]) -> PharmacyIntentResult:
        """Analyze message using spaCy NLU with database patterns."""
        if self.nlp is None:
            return await self._keyword_fallback(message, context)

        text_lower = message.lower().strip()
        doc = self.nlp(text_lower)

        # Priority 1: Check confirmation context first
        if context.get("awaiting_confirmation"):
            if result := self._match_confirmation(text_lower):
                return result

        # Priority 2: Check document input context - detect DNI when awaiting document
        if context.get("awaiting_document_input"):
            dni_match = re.search(r"\d{7,8}", text_lower)
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
        if result := self._match_greeting(text_lower):
            return result

        # Extract entities early for payment detection
        entities = self._entity_extractor.extract(doc, text_lower)

        # Priority 3b: Detect capability/info questions
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
        if is_payment_intent_from_patterns(text_lower, entities, self._patterns):
            return PharmacyIntentResult(
                intent="invoice",
                confidence=CONFIDENCE_EXACT_MATCH,
                is_out_of_scope=False,
                entities=entities,
                method="payment_detection",
                analysis={"detected": "payment_with_amount"},
            )

        # Check if we have patterns configured
        intent_patterns = self._patterns.get("intents", {}) if self._patterns else {}
        if not intent_patterns:
            return PharmacyIntentResult(
                intent="unknown",
                confidence=0.0,
                is_out_of_scope=True,
                entities=entities,
                method="no_patterns_configured",
                analysis={"error": "No patterns in database for this organization"},
            )

        # Score all intents from database patterns
        lemmas = {token.lemma_.lower() for token in doc if not token.is_stop and not token.is_punct}
        scores = {
            intent: self._calculate_intent_score(text_lower, lemmas, patterns, doc)
            for intent, patterns in intent_patterns.items()
        }

        best_intent, best_score = max(scores.items(), key=lambda x: x[1])
        is_out_of_scope = best_score < CONFIDENCE_OUT_OF_SCOPE

        return PharmacyIntentResult(
            intent=best_intent if not is_out_of_scope else "unknown",
            confidence=min(best_score, CONFIDENCE_MAX_SPACY),
            is_out_of_scope=is_out_of_scope,
            entities=entities,
            method="spacy_db",
            analysis={"lemmas": list(lemmas), "scores": scores, "token_count": len(doc)},
        )

    def _match_confirmation(self, text_lower: str) -> PharmacyIntentResult | None:
        """Match confirmation patterns from database."""
        if not self._patterns:
            return None

        confirmation_patterns = self._patterns.get("confirmation_patterns", {})

        for intent_key, patterns in confirmation_patterns.items():
            exact_patterns = patterns.get("exact", set())
            contains_patterns = patterns.get("contains", set())

            # Convert lists to sets if needed (from JSON deserialization)
            if isinstance(exact_patterns, list):
                exact_patterns = set(exact_patterns)
            if isinstance(contains_patterns, list):
                contains_patterns = set(contains_patterns)

            if text_lower in exact_patterns:
                return PharmacyIntentResult(
                    intent=intent_key,
                    confidence=CONFIDENCE_EXACT_MATCH,
                    method="pattern_match_db",
                    analysis={"matched": text_lower, "type": "exact"},
                )

            for pattern in contains_patterns:
                if pattern in text_lower:
                    return PharmacyIntentResult(
                        intent=intent_key,
                        confidence=CONFIDENCE_CONTAINS,
                        method="pattern_match_db",
                        analysis={"matched": pattern, "type": "contains"},
                    )

        return None

    def _match_greeting(self, text_lower: str) -> PharmacyIntentResult | None:
        """Match greeting patterns from database."""
        if not self._patterns:
            return None

        greeting_patterns = self._patterns.get("greeting_patterns", {})

        exact = greeting_patterns.get("exact", set())
        prefixes = greeting_patterns.get("prefixes", [])

        # Convert lists to sets if needed
        if isinstance(exact, list):
            exact = set(exact)

        if text_lower in exact:
            return PharmacyIntentResult(
                intent="greeting",
                confidence=CONFIDENCE_EXACT_MATCH,
                method="greeting_db",
                analysis={"matched": text_lower, "type": "exact"},
            )

        for prefix in prefixes:
            if text_lower.startswith(prefix):
                return PharmacyIntentResult(
                    intent="greeting",
                    confidence=CONFIDENCE_CONTAINS,
                    method="greeting_db",
                    analysis={"matched": prefix, "type": "prefix"},
                )

        return None

    def _calculate_intent_score(
        self,
        text_lower: str,
        lemmas: set[str],
        patterns: dict[str, Any],
        _doc: Any,  # Unused, kept for future POS tag analysis
    ) -> float:
        """Calculate score for a single intent based on database patterns."""
        del _doc  # Explicitly mark as unused (reserved for future POS tag analysis)
        score = 0.0
        weight = patterns.get("weight", 1.0)
        exact_match = patterns.get("exact_match", False)

        # Lemma matching
        intent_lemmas = set(patterns.get("lemmas", []))
        if lemma_matches := lemmas & intent_lemmas:
            score += len(lemma_matches) * 0.4

        # Phrase matching
        for phrase_data in patterns.get("phrases", []):
            phrase = phrase_data.get("phrase", "") if isinstance(phrase_data, dict) else phrase_data
            match_type = phrase_data.get("match_type", "contains") if isinstance(phrase_data, dict) else "contains"

            if exact_match or match_type == "exact":
                if text_lower == phrase or text_lower.startswith(f"{phrase} "):
                    score += 0.9
                    break
            elif match_type == "prefix":
                if text_lower.startswith(phrase):
                    score += 0.5
            elif phrase in text_lower:  # contains
                score += 0.5

        return min(score * weight, 1.0)

    def _is_capability_question(self, text: str) -> bool:
        """Check if message is asking about bot capabilities.

        Uses database patterns from capability_question intent when available,
        with hardcoded fallback for backward compatibility.
        """
        text_lower = text.lower()

        # Try database patterns first (from capability_question intent)
        if self._patterns:
            capability = self._patterns.get("intents", {}).get("capability_question", {})
            phrases = capability.get("phrases", [])
            if phrases:
                # Database patterns available - use them
                for p in phrases:
                    if isinstance(p, dict) and "phrase" in p:
                        if p["phrase"].lower() in text_lower:
                            return True
                return False

        # Fallback to hardcoded patterns (if no DB patterns)
        capability_phrases = (
            "que puedes hacer",
            "qué puedes hacer",
            "que puedes",
            "qué puedes",
            "puedes hacer",
            "que haces",
            "qué haces",
            "que sabes",
            "qué sabes",
            "para que sirves",
            "para qué sirves",
            "que servicios",
            "qué servicios",
            "como funciona",
            "cómo funciona",
        )
        return any(phrase in text_lower for phrase in capability_phrases)

    async def _keyword_fallback(self, message: str, context: dict[str, Any]) -> PharmacyIntentResult:
        """Keyword fallback when spaCy unavailable, using database patterns."""
        text_lower = message.lower().strip()

        if context.get("awaiting_confirmation"):
            if result := self._match_confirmation(text_lower):
                return result

        keyword_patterns = self._patterns.get("keyword_patterns", {}) if self._patterns else {}

        for intent, keywords in keyword_patterns.items():
            if any(kw in text_lower for kw in keywords):
                return PharmacyIntentResult(
                    intent=intent,
                    confidence=0.7,
                    method="keyword_fallback_db",
                )

        return PharmacyIntentResult(
            intent="unknown",
            confidence=0.3,
            is_out_of_scope=True,
            method="keyword_fallback_db",
        )

    async def _analyze_with_llm(
        self,
        message: str,
        context: dict[str, Any],
        spacy_result: PharmacyIntentResult,
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
        """Build prompt using loaded YAML template."""
        # Ensure templates are loaded
        await self._ensure_templates_loaded()

        conversation_history = context.get("conversation_history", "")
        if not conversation_history:
            conversation_history = "(Sin historial previo - primer mensaje)"

        # Get template or use fallback
        template = self._prompt_templates.get("pharmacy.intent_analyzer.main", "")
        if not template:
            # Minimal fallback if template not loaded
            template = """Analiza el mensaje y determina la intención.
Mensaje: "{message}"
Responde con JSON: intent, confidence, is_out_of_scope"""

        # Render template with variables
        return template.format(
            message=message,
            customer_identified=context.get("customer_identified", False),
            awaiting_confirmation=context.get("awaiting_confirmation", False),
            awaiting_document_input=context.get("awaiting_document_input", False),
            debt_status=context.get("debt_status", "none"),
            capabilities="\n".join(f"- {cap}" for cap in PHARMACY_CAPABILITIES),
            conversation_history=conversation_history,
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

            # Validate intent against database patterns
            valid_intents = self._patterns.get("valid_intents", set()) if self._patterns else set()
            if isinstance(valid_intents, list):
                valid_intents = set(valid_intents)
            if intent not in valid_intents:
                intent = "unknown"

            # Ensure entities is a dict before merging
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
        valid_intents = self._patterns.get("valid_intents", set()) if self._patterns else set()
        if isinstance(valid_intents, list):
            valid_intents = set(valid_intents)

        org_id = self._current_org_id or self._organization_id

        return {
            "spacy_available": self.nlp is not None,
            "spacy_model": self.model_name,
            "llm_fallback_enabled": self.use_llm_fallback,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "valid_intents": list(valid_intents),
            "patterns_loaded": self._patterns is not None and bool(self._patterns),
            "organization_id": str(org_id) if org_id else None,
            "multi_tenant_mode": self._organization_id is None,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_pharmacy_intent_analyzer(
    db: "AsyncSession | None" = None,
    organization_id: UUID | None = None,
    use_llm_fallback: bool = True,
) -> PharmacyIntentAnalyzer:
    """
    Factory function to create a PharmacyIntentAnalyzer instance.

    This is the recommended way to create analyzer instances, especially
    in multi-tenant scenarios where db and organization_id may not be
    available at construction time.

    Args:
        db: Optional AsyncSession for database access
        organization_id: Optional tenant UUID for loading patterns
        use_llm_fallback: Enable LLM fallback for low confidence (default True)

    Returns:
        Configured PharmacyIntentAnalyzer instance

    Usage:
        # Multi-tenant (recommended) - pass org_id to analyze()
        analyzer = get_pharmacy_intent_analyzer()
        result = await analyzer.analyze(msg, ctx, organization_id=org_id)

        # With db session available
        analyzer = get_pharmacy_intent_analyzer(db=session)
        result = await analyzer.analyze(msg, ctx, organization_id=org_id)

        # Single-tenant with all params
        analyzer = get_pharmacy_intent_analyzer(db=session, organization_id=org_id)
        result = await analyzer.analyze(msg, ctx)
    """
    return PharmacyIntentAnalyzer(
        db=db,
        organization_id=organization_id,
        use_llm_fallback=use_llm_fallback,
    )
