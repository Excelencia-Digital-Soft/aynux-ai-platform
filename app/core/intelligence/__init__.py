"""Intelligence module for intent routing and analysis.

Provides:
- IntentRouter: Orchestrator with three-tier fallback (LLM → SpaCy → Keywords)
- SpacyIntentAnalyzer: NLP-based intent analysis
- IIntentAnalyzer: Protocol for custom analyzers

Components (SRP-compliant):
- analyzers/: Intent analyzers (LLM, Keyword, Protocol)
- cache/: LRU cache with TTL
- validators/: Intent validation and agent mapping
- metrics/: Performance tracking
"""

from app.core.intelligence.analyzers.protocol import IIntentAnalyzer
from app.core.intelligence.intent_router import IntentRouter
from app.core.intelligence.spacy_intent_analyzer import SpacyIntentAnalyzer

__all__ = [
    "IntentRouter",
    "SpacyIntentAnalyzer",
    "IIntentAnalyzer",
]
