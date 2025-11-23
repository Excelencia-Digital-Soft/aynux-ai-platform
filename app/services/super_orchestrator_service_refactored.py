"""
Super Orchestrator Service - REFACTORED following SOLID principles.

This is a refactored version that delegates responsibilities to specialized components:
- DomainClassifier: Handles domain classification
- ClassificationStatisticsTracker: Handles metrics tracking
- DomainPatternRepository: Handles pattern storage

Original file had 496 lines with multiple responsibilities.
Refactored version: ~150 lines focused on orchestration only.
"""

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.services.domain_detector import get_domain_detector
from app.services.domain_manager import get_domain_manager
from app.services.orchestration import (
    ClassificationStatisticsTracker,
    DomainClassifier,
    DomainPatternRepository,
)

logger = logging.getLogger(__name__)


class SuperOrchestratorServiceRefactored:
    """
    Super Orchestrator que usa IA para clasificar mensajes de dominio.

    REFACTORED siguiendo SOLID principles:
    - SRP: Solo se encarga de orquestar el flujo de clasificación y procesamiento
    - DIP: Depende de abstracciones (DomainClassifier, etc.)
    - OCP: Abierto a extensión a través de dependency injection

    Responsabilidades delegadas:
    - Classification: DomainClassifier
    - Statistics: ClassificationStatisticsTracker
    - Patterns: DomainPatternRepository
    - Domain detection: DomainDetector (existing)
    - Domain services: DomainManager (existing)
    """

    def __init__(
        self,
        classifier: DomainClassifier | None = None,
        statistics_tracker: ClassificationStatisticsTracker | None = None,
        pattern_repository: DomainPatternRepository | None = None,
    ):
        """
        Initialize super orchestrator with dependency injection.

        Args:
            classifier: Domain classifier (creates default if None)
            statistics_tracker: Statistics tracker (creates default if None)
            pattern_repository: Pattern repository (creates default if None)
        """
        self.settings = get_settings()

        # Dependency injection - allows for testing and flexibility
        self.pattern_repository = pattern_repository or DomainPatternRepository()
        self.classifier = classifier or DomainClassifier(
            pattern_repository=self.pattern_repository,
            model=getattr(self.settings, "SUPER_ORCHESTRATOR_MODEL", "deepseek-r1:7b"),
        )
        self.statistics_tracker = statistics_tracker or ClassificationStatisticsTracker()

        # External dependencies
        self.domain_detector = get_domain_detector()
        self.domain_manager = get_domain_manager()

        # Configuration
        self.confidence_threshold = getattr(self.settings, "SUPER_ORCHESTRATOR_CONFIDENCE_THRESHOLD", 0.7)

        logger.info(
            f"SuperOrchestratorServiceRefactored initialized "
            f"(confidence_threshold: {self.confidence_threshold})"
        )

    async def process_webhook_message(
        self,
        message: WhatsAppMessage,
        contact: Contact,
        db_session: AsyncSession,
    ) -> BotResponse:
        """
        Process WhatsApp message using intelligent domain classification.

        Orchestration flow:
        1. Extract message text
        2. Classify domain using AI/keywords
        3. Persist classification if confidence is sufficient
        4. Get appropriate domain service
        5. Process message with domain service
        6. Track statistics

        Args:
            message: WhatsApp message
            contact: Contact information
            db_session: Database session

        Returns:
            Bot response from appropriate domain service
        """
        start_time = time.time()
        wa_id = contact.wa_id
        message_text = self._extract_message_text(message)

        logger.info(f"SuperOrchestrator processing contact: {wa_id}")

        try:
            # Step 1: Classify domain
            classification = await self.classifier.classify(message_text, contact)

            logger.info(
                f"Domain classified: {wa_id} -> {classification.domain} "
                f"(confidence: {classification.confidence:.2f}, method: {classification.method})"
            )

            # Step 2: Persist classification if confidence is sufficient
            successful = classification.confidence >= self.confidence_threshold

            if successful:
                await self.domain_detector.assign_domain(
                    wa_id=wa_id,
                    domain=classification.domain,
                    method=classification.method,
                    confidence=classification.confidence,
                    db_session=db_session,
                )
            else:
                logger.warning(
                    f"Low confidence classification: {wa_id} -> "
                    f"{classification.domain} ({classification.confidence:.2f})"
                )

            # Step 3: Get domain service
            domain_service = await self.domain_manager.get_service(classification.domain)

            if not domain_service:
                logger.error(f"Domain service not available: {classification.domain}")
                return self._create_error_response("Lo siento, el servicio no está disponible en este momento.")

            # Step 4: Process with domain service
            response = await domain_service.process_webhook_message(message, contact)

            # Step 5: Track statistics
            classification_time_ms = (time.time() - start_time) * 1000
            self.statistics_tracker.record_classification(
                domain=classification.domain,
                confidence=classification.confidence,
                method=classification.method,
                classification_time_ms=classification_time_ms,
                successful=successful,
            )

            return response

        except Exception as e:
            logger.error(f"Error in super orchestrator processing: {e}", exc_info=True)

            # Fallback to default domain
            return await self._handle_error_fallback(message, contact)

    async def _handle_error_fallback(
        self,
        message: WhatsAppMessage,
        contact: Contact,
    ) -> BotResponse:
        """
        Handle error with fallback to default domain.

        Args:
            message: WhatsApp message
            contact: Contact information

        Returns:
            Bot response from default domain or error message
        """
        default_domain = getattr(self.settings, "DEFAULT_DOMAIN", "ecommerce")
        logger.info(f"Falling back to default domain: {default_domain}")

        domain_service = await self.domain_manager.get_service(default_domain)

        if domain_service:
            try:
                return await domain_service.process_webhook_message(message, contact)
            except Exception as e:
                logger.error(f"Fallback domain service also failed: {e}")

        return self._create_error_response("Lo siento, hay un problema técnico. Por favor intenta más tarde.")

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """
        Extract text from WhatsApp message.

        Args:
            message: WhatsApp message

        Returns:
            Extracted text
        """
        if message.type == "text":
            return message.text.body if message.text else ""
        elif message.type == "interactive":
            if message.interactive and message.interactive.button_reply:
                return message.interactive.button_reply.title
            elif message.interactive and message.interactive.list_reply:
                return message.interactive.list_reply.title
        return ""

    def _create_error_response(self, error_message: str) -> BotResponse:
        """
        Create error response.

        Args:
            error_message: Error message to send to user

        Returns:
            BotResponse with error status
        """
        return BotResponse(
            status="failure",
            message=error_message,
        )

    def get_stats(self) -> dict[str, Any]:
        """
        Get orchestration statistics.

        Returns:
            Statistics dictionary from tracker
        """
        return self.statistics_tracker.get_stats()

    async def test_classification(self, message: str) -> dict[str, Any]:
        """
        Test classification with detailed output.

        Useful for debugging and validating classification logic.

        Args:
            message: Message to classify

        Returns:
            Detailed classification results
        """
        return await self.classifier.test_classification(message)

    def reset_stats(self) -> None:
        """Reset statistics tracker."""
        self.statistics_tracker.reset()

    def get_pattern_stats(self) -> dict[str, Any]:
        """Get pattern repository statistics."""
        return self.pattern_repository.get_stats()


# Singleton instance
_orchestrator_instance: SuperOrchestratorServiceRefactored | None = None


def get_super_orchestrator_refactored() -> SuperOrchestratorServiceRefactored:
    """
    Get singleton instance of refactored super orchestrator.

    Returns:
        SuperOrchestratorServiceRefactored instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = SuperOrchestratorServiceRefactored()

    return _orchestrator_instance
