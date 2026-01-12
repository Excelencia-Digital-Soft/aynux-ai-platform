# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Intent patterns module.
# ============================================================================
"""Intent Patterns.

Strategy pattern implementations for intent detection.
Each pattern handles a specific type of user intent.
"""

from .base import IntentPattern, IntentResult
from .document import DocumentPattern
from .greeting import GreetingPattern
from .interactive import InteractivePattern
from .management import ManagementPattern

__all__ = [
    "IntentPattern",
    "IntentResult",
    "GreetingPattern",
    "DocumentPattern",
    "ManagementPattern",
    "InteractivePattern",
]
