"""Constants for PersonResolution flow."""

from __future__ import annotations

# Identification flow step identifiers
STEP_AWAITING_WELCOME = "awaiting_welcome"
STEP_AWAITING_IDENTIFIER = "awaiting_identifier"
STEP_NAME = "name"

# Validation thresholds
MAX_IDENTIFICATION_RETRIES = 3
NAME_MATCH_THRESHOLD = 0.75

# Welcome response options
WELCOME_OPTIONS: dict[str, list[str]] = {
    "existing_client": ["1", "1️⃣", "si", "sí", "cliente", "soy cliente"],
    "new_client": ["2", "2️⃣", "no", "registrar", "registrarme", "nuevo"],
    "info_only": ["3", "3️⃣", "info", "información", "informacion", "solo info"],
}

# Own/other response indicators
OWN_INDICATORS = ["1", "mi deuda", "propia", "mia", "mi", "yo"]
OTHER_INDICATORS = ["2", "otra persona", "otro", "otra", "familiar", "tercero"]

__all__ = [
    "STEP_AWAITING_WELCOME",
    "STEP_AWAITING_IDENTIFIER",
    "STEP_NAME",
    "MAX_IDENTIFICATION_RETRIES",
    "NAME_MATCH_THRESHOLD",
    "WELCOME_OPTIONS",
    "OWN_INDICATORS",
    "OTHER_INDICATORS",
]
