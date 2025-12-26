"""
Smart Input Interpreter module.

Provides intelligent input interpretation with LLM fallback for:
- Priority selection
- Confirmation responses
- Description quality validation
- Incident intent detection
"""

from .base import InterpretationResult
from .facade import SmartInputInterpreter

__all__ = ["SmartInputInterpreter", "InterpretationResult"]
