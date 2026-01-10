"""
Pharmacy Intent Patterns

Confidence thresholds and domain capabilities for pharmacy intent analysis.

NOTE: Intent patterns (lemmas, phrases, keywords, confirmations) are now
stored in the database tables:
- core.pharmacy_intents
- core.pharmacy_intent_lemmas
- core.pharmacy_intent_phrases
- core.pharmacy_confirmation_patterns
- core.pharmacy_keyword_patterns

Use seed_pharmacy_intents.py to populate the database with patterns.
"""

from __future__ import annotations

# Confidence thresholds (single source of truth)
CONFIDENCE_THRESHOLD = 0.6  # LLM fallback threshold
CONFIDENCE_OUT_OF_SCOPE = 0.3
CONFIDENCE_MAX_SPACY = 0.95
CONFIDENCE_EXACT_MATCH = 0.95
CONFIDENCE_CONTAINS = 0.85

# Pharmacy domain capabilities (used in prompts, not for pattern matching)
PHARMACY_CAPABILITIES = [
    "consultar deuda/saldo pendiente",
    "confirmar deuda para pago",
    "generar recibo/factura",
    "registrarse como cliente nuevo",
    "consultar información de la farmacia (dirección, teléfono, horario)",
]
