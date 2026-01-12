# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Intent detection module.
# ============================================================================
"""Intent Detection Module.

Provides extensible intent detection using Strategy pattern.

Components:
- IntentDetector: Orchestrates pattern detection
- IntentPattern: Abstract base for patterns
- IntentResult: Detection result container
- Patterns: Greeting, Document, Management, Interactive

Usage:
    from .intent import IntentDetector, create_default_detector

    # Use default patterns
    detector = create_default_detector()
    result = detector.detect(message, state)

    # Or customize patterns
    detector = IntentDetector()
    detector.add_pattern(MyCustomPattern())
"""

from .detector import IntentDetector, create_default_detector
from .patterns import (
    DocumentPattern,
    GreetingPattern,
    IntentPattern,
    IntentResult,
    InteractivePattern,
    ManagementPattern,
)

__all__ = [
    "IntentDetector",
    "create_default_detector",
    "IntentPattern",
    "IntentResult",
    "GreetingPattern",
    "DocumentPattern",
    "ManagementPattern",
    "InteractivePattern",
]
