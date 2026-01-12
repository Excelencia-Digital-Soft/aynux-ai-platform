"""Constants for PersonResolution flow."""

from __future__ import annotations

# Identification flow step identifiers
STEP_AWAITING_WELCOME = "awaiting_welcome"
STEP_AWAITING_IDENTIFIER = "awaiting_identifier"
STEP_NAME = "name"
STEP_AWAITING_ACCOUNT_SELECTION = "awaiting_account_selection"

# Registration flow steps
REGISTRATION_STEP_NAME = "nombre"
REGISTRATION_STEP_DOCUMENT = "documento"
REGISTRATION_STEP_CONFIRM = "confirmar"

# Validation thresholds
MAX_IDENTIFICATION_RETRIES = 3
NAME_MATCH_THRESHOLD = 0.75

# NOTE: WELCOME_OPTIONS, OWN_INDICATORS, OTHER_INDICATORS moved to database
# See core.domain_intents table with intent_keys:
# - welcome_existing_client, welcome_new_client, welcome_info_only
# - own_or_other_own, own_or_other_other
# Use domain_intent_cache.get_patterns() to load patterns from DB

__all__ = [
    "STEP_AWAITING_WELCOME",
    "STEP_AWAITING_IDENTIFIER",
    "STEP_NAME",
    "STEP_AWAITING_ACCOUNT_SELECTION",
    "REGISTRATION_STEP_NAME",
    "REGISTRATION_STEP_DOCUMENT",
    "REGISTRATION_STEP_CONFIRM",
    "MAX_IDENTIFICATION_RETRIES",
    "NAME_MATCH_THRESHOLD",
]
