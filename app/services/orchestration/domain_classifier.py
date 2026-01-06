"""
Domain Classifier - Componente especializado en clasificación de dominios.

Sigue el Single Responsibility Principle: solo se encarga de clasificar
mensajes en dominios de negocio usando múltiples estrategias.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.integrations.llm import VllmLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.models.message import Contact
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry
from app.services.orchestration.domain_pattern_repository import DomainPatternRepository

logger = logging.getLogger(__name__)


class ClassificationResult:
    """Value object para resultados de clasificación."""

    def __init__(
        self,
        domain: str,
        confidence: float,
        method: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize classification result.

        Args:
            domain: Dominio clasificado (ecommerce, hospital, credit)
            confidence: Nivel de confianza (0.0-1.0)
            method: Método usado (keyword, ai, hybrid)
            metadata: Información adicional sobre la clasificación
        """
        self.domain = domain
        self.confidence = confidence
        self.method = method
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "domain": self.domain,
            "confidence": self.confidence,
            "method": self.method,
            "metadata": self.metadata,
        }


class DomainClassifier:
    """
    Clasificador de dominios usando múltiples estrategias.

    Aplica Single Responsibility Principle:
    - Solo se encarga de clasificar dominios
    - No maneja estadísticas
    - No maneja procesamiento de mensajes
    - No almacena configuración (usa repository)

    Aplica Strategy Pattern:
    - Keyword-based classification
    - AI-based classification
    - Hybrid classification
    """

    def __init__(
        self,
        pattern_repository: DomainPatternRepository,
        llm: VllmLLM | None = None,
    ):
        """
        Initialize domain classifier.

        Args:
            pattern_repository: Repository for domain patterns
            llm: VllmLLM instance for AI classification
        """
        self.pattern_repository = pattern_repository
        self.llm = llm or VllmLLM()
        self.settings = get_settings()

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

    async def classify(
        self,
        message: str,
        contact: Contact | None = None,
    ) -> ClassificationResult:
        """
        Classify message into business domain.

        Uses hybrid approach:
        1. Try keyword-based classification (fast)
        2. If confidence low, use AI classification
        3. Return best result

        Args:
            message: User message text
            contact: Optional contact information for context

        Returns:
            ClassificationResult with domain and confidence
        """
        message_lower = message.lower()

        # Strategy 1: Keyword-based classification (fast, deterministic)
        keyword_result = self._classify_by_keywords(message_lower)

        # If keyword confidence is high, return immediately
        if keyword_result.confidence >= 0.8:
            logger.debug(
                f"High confidence keyword classification: " f"{keyword_result.domain} ({keyword_result.confidence:.2f})"
            )
            return keyword_result

        # Strategy 2: AI-based classification (slower, more accurate)
        try:
            ai_result = await self._classify_with_ai(message, contact)

            # Use AI result if confidence is higher
            if ai_result.confidence > keyword_result.confidence:
                logger.debug(
                    f"AI classification selected: "
                    f"{ai_result.domain} ({ai_result.confidence:.2f}) "
                    f"over keyword ({keyword_result.confidence:.2f})"
                )
                return ai_result

        except Exception as e:
            logger.warning(f"AI classification failed, using keyword result: {e}")

        # Fallback to keyword result
        return keyword_result

    def _classify_by_keywords(self, message: str) -> ClassificationResult:
        """
        Classify using keyword matching.

        Args:
            message: Lowercase message text

        Returns:
            ClassificationResult with keyword-based classification
        """
        domain_scores: dict[str, float] = {}
        all_domains = self.pattern_repository.get_all_domains()

        for domain in all_domains:
            score = 0.0
            matches = []

            # Check keywords
            keywords = self.pattern_repository.get_keywords(domain)
            for keyword in keywords:
                if keyword in message:
                    score += 1.0
                    matches.append(f"keyword:{keyword}")

            # Check phrases (worth more)
            phrases = self.pattern_repository.get_phrases(domain)
            for phrase in phrases:
                if phrase in message:
                    score += 2.0
                    matches.append(f"phrase:{phrase}")

            # Check indicators
            indicators = self.pattern_repository.get_indicators(domain)
            for indicator in indicators:
                if indicator in message:
                    score += 1.5
                    matches.append(f"indicator:{indicator}")

            if score > 0:
                domain_scores[domain] = score
                logger.debug(f"Domain {domain} score: {score:.1f} (matches: {matches})")

        # Determine best domain
        if not domain_scores:
            # No matches - return default
            return ClassificationResult(
                domain="excelencia",  # Default domain
                confidence=0.3,
                method="keyword_default",
                metadata={"reason": "no_keyword_matches"},
            )

        # Get domain with highest score
        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]

        # Normalize confidence (max score of ~10 keywords = confidence 1.0)
        confidence = min(best_score / 10.0, 1.0)

        # Boost confidence if significantly higher than other domains
        scores_sorted = sorted(domain_scores.values(), reverse=True)
        if len(scores_sorted) > 1 and scores_sorted[0] > scores_sorted[1] * 2:
            confidence = min(confidence * 1.2, 1.0)

        return ClassificationResult(
            domain=best_domain,
            confidence=confidence,
            method="keyword",
            metadata={
                "scores": domain_scores,
                "total_matches": int(best_score),
            },
        )

    async def _classify_with_ai(
        self,
        message: str,
        contact: Contact | None = None,
    ) -> ClassificationResult:
        """
        Classify using AI (LLM).

        Args:
            message: User message
            contact: Optional contact for context

        Returns:
            ClassificationResult with AI-based classification
        """
        # Build context
        available_domains = self.pattern_repository.get_all_domains()
        domain_descriptions = []

        for domain in available_domains:
            desc = self.pattern_repository.get_description(domain)
            domain_descriptions.append(f"- {domain}: {desc}")

        context_info = ""
        if contact:
            context_info = f"\nContexto del usuario: {contact.name or contact.wa_id}"

        # Build prompt from YAML
        try:
            prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.ORCHESTRATOR_DOMAIN_CLASSIFICATION,
                variables={
                    "message": message,
                    "context_info": context_info,
                    "domain_descriptions": "\n".join(domain_descriptions),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            # Fallback to hardcoded prompt
            prompt = (
                f"# CLASIFICACIÓN DE DOMINIO DE NEGOCIO\n\n"
                f'MENSAJE DEL USUARIO:\n"{message}"\n{context_info}\n\n'
                f"DOMINIOS DISPONIBLES:\n{chr(10).join(domain_descriptions)}\n\n"
                "INSTRUCCIONES:\nAnaliza el mensaje y determina a qué dominio corresponde.\n"
                'Responde SOLO con JSON: {"domain": "...", "confidence": 0.0-1.0}'
            )

        try:
            # Call LLM
            llm = self.llm.get_llm(complexity=ModelComplexity.SIMPLE, temperature=0.2)
            response = await llm.ainvoke(prompt)

            # Parse response
            from app.utils import extract_json_from_text

            content = response.content if isinstance(response.content, str) else str(response.content)
            result_dict = extract_json_from_text(
                content,
                default={"domain": "excelencia", "confidence": 0.4},
                required_keys=["domain"],
            )

            if not result_dict or not isinstance(result_dict, dict):
                result_dict = {"domain": "excelencia", "confidence": 0.4}

            domain = result_dict.get("domain", "excelencia")
            confidence = float(result_dict.get("confidence", 0.5))
            reasoning = result_dict.get("reasoning", "")

            return ClassificationResult(
                domain=domain,
                confidence=confidence,
                method="ai",
                metadata={"reasoning": reasoning, "model": self.settings.VLLM_MODEL},
            )

        except Exception as e:
            logger.error(f"AI classification error: {e}")
            # Return low-confidence default
            return ClassificationResult(
                domain="excelencia",
                confidence=0.4,
                method="ai_error",
                metadata={"error": str(e)},
            )

    async def test_classification(self, message: str) -> dict[str, Any]:
        """
        Test classification with detailed output.

        Args:
            message: Message to classify

        Returns:
            Detailed classification results for testing
        """
        keyword_result = self._classify_by_keywords(message.lower())
        ai_result = await self._classify_with_ai(message)
        final_result = await self.classify(message)

        return {
            "message": message,
            "keyword_classification": keyword_result.to_dict(),
            "ai_classification": ai_result.to_dict(),
            "final_classification": final_result.to_dict(),
            "comparison": {
                "keyword_confidence": keyword_result.confidence,
                "ai_confidence": ai_result.confidence,
                "final_confidence": final_result.confidence,
                "method_used": final_result.method,
            },
        }
