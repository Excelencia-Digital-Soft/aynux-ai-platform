# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: NLU (Natural Language Understanding) system for intent detection
#              and entity extraction in medical appointment conversations.
# ============================================================================
"""Medical Appointments NLU System.

Provides natural language understanding capabilities for the medical
appointments domain, enabling intelligent routing and entity extraction.

Usage:
    from .nlu import MedicalIntentDetector, MedicalEntityExtractor, NLURouter

    # Intent detection
    detector = MedicalIntentDetector()
    intent_result = await detector.detect(message, context)

    # Entity extraction
    extractor = MedicalEntityExtractor()
    entities = await extractor.extract(message)

    # Combined NLU routing
    router = NLURouter(detector, extractor)
    nlu_result = await router.process(message, context)
"""

from .entity_extractor import MedicalEntityExtractor
from .intent_detector import MedicalIntentDetector, MedicalIntentResult
from .nlu_router import NLUResult, NLURouter

__all__ = [
    # Intent Detection
    "MedicalIntentDetector",
    "MedicalIntentResult",
    # Entity Extraction
    "MedicalEntityExtractor",
    # NLU Router
    "NLURouter",
    "NLUResult",
]
