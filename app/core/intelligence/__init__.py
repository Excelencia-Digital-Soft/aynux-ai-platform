"""
Intelligence module for intent routing and analysis.

Provides:
- IntentRouter: LLM-based intent classification
- SpacyIntentAnalyzer: NLP-based intent analysis
"""

from app.core.intelligence.intent_router import IntentRouter
from app.core.intelligence.spacy_intent_analyzer import SpacyIntentAnalyzer

__all__ = [
    "IntentRouter",
    "SpacyIntentAnalyzer",
]
