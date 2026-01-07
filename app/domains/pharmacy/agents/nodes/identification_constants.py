"""
Identification Constants

Constants for the customer identification flow.
Single responsibility: centralized constants for identification logic.
"""

from __future__ import annotations

import re

# Out-of-scope intents that should bypass DNI request
OUT_OF_SCOPE_INTENTS: frozenset[str] = frozenset({
    "out_of_scope",
    "info_query",
    "farewell",
    "thanks",
    "unknown",
})

# Keywords that indicate message is clearly NOT about debt/payment (for unidentified users)
OUT_OF_SCOPE_KEYWORDS: tuple[str, ...] = (
    # Precios y costos
    "precio",
    "costo",
    "cuanto sale",
    "cuanto cuesta",
    # Contacto e informacion
    "contacto",
    "contactar",
    "telefono",
    "horario",
    "direccion",
    "ubicacion",
    "donde quedan",
    "donde estan",
    # Canales de contacto
    "otros canales",
    "que canales",
    "canales de",
    "otros medios",
    "otras formas",
    "formas de contacto",
    # Preguntas sobre capacidades (fuera de alcance sin identificacion)
    "que puedes",
    "que podes",
    "que haces",
    "que hace",
    "que mas",
    "para que",
    "como funciona",
    "que servicios",
    "ayuda con",
    "puedes hacer",
    "podes hacer",
    "sabes hacer",
    # Despedidas y agradecimientos
    "gracias",
    "chau",
    "adios",
    "hasta luego",
    "nos vemos",
    "bye",
)

# DNI patterns for detecting document numbers in messages
# Pattern 1: Pure digits standing alone (7-8 digits)
DNI_PATTERN_PURE: re.Pattern[str] = re.compile(r"^\s*(\d{7,8})\s*$")

# Pattern 2: DNI in natural language ("mi documento es 2259863", "DNI: 2259863")
DNI_PATTERN_NATURAL: re.Pattern[str] = re.compile(
    r"(?:mi\s+)?(?:dni|documento|doc|nro|numero|número)[\s:]+(?:es\s+)?(\d{7,8})",
    re.IGNORECASE,
)

# Pattern 3: "soy" + number pattern ("soy 12345678")
DNI_PATTERN_SOY: re.Pattern[str] = re.compile(
    r"(?:soy|es)\s+(\d{7,8})\b",
    re.IGNORECASE,
)

# List of patterns to try in order (most specific first)
DNI_PATTERNS: list[re.Pattern[str]] = [
    DNI_PATTERN_PURE,
    DNI_PATTERN_NATURAL,
    DNI_PATTERN_SOY,
]

# Legacy alias for backward compatibility
DNI_PATTERN: re.Pattern[str] = DNI_PATTERN_PURE

# Minimum document length for validation
MIN_DOCUMENT_LENGTH: int = 6
