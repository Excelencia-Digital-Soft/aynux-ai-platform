"""Add account selection intent patterns for System Organization.

Revision ID: nn3o4p5q6r7s
Revises: mm2n3o4p5q6r
Create Date: 2026-01-12

Adds the 3 account selection intents that were missing from System Org:
1. account_selection_existing - for selecting existing account
2. account_selection_new - for creating new account
3. affirmative_response - for general affirmative responses

These were previously only added to Org 1 in migration ii8j9k0l1m2n.
"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "nn3o4p5q6r7s"
down_revision: Union[str, Sequence[str], None] = "mm2n3o4p5q6r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System Organization UUID (used in production)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"
DOMAIN_KEY = "pharmacy"


def upgrade() -> None:
    """Add account selection intent patterns for System Org."""
    intents = _get_account_selection_intents()

    for intent_key, data in intents.items():
        name = data.get("name", intent_key).replace("'", "''")
        description = (data.get("description") or "").replace("'", "''")

        lemmas = json.dumps(data.get("lemmas", []))
        phrases = json.dumps(data.get("phrases", []))
        confirmation_patterns = json.dumps(data.get("confirmation_patterns", []))
        keywords = json.dumps(data.get("keywords", []))

        op.execute(f"""
            INSERT INTO core.domain_intents (
                organization_id, domain_key, intent_key,
                name, description, weight, exact_match, priority, is_enabled,
                lemmas, phrases, confirmation_patterns, keywords
            ) VALUES (
                '{SYSTEM_ORG_ID}',
                '{DOMAIN_KEY}',
                '{intent_key}',
                '{name}',
                '{description}',
                {data.get('weight', 1.0)},
                {str(data.get('exact_match', False)).lower()},
                {data.get('priority', 50)},
                {str(data.get('is_enabled', True)).lower()},
                '{lemmas}'::jsonb,
                '{phrases}'::jsonb,
                '{confirmation_patterns}'::jsonb,
                '{keywords}'::jsonb
            )
            ON CONFLICT (organization_id, domain_key, intent_key) DO UPDATE SET
                confirmation_patterns = EXCLUDED.confirmation_patterns,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = NOW()
        """)


def downgrade() -> None:
    """Remove account selection intent patterns from System Org."""
    intent_keys = [
        "account_selection_existing",
        "account_selection_new",
        "affirmative_response",
    ]

    for intent_key in intent_keys:
        op.execute(f"""
            DELETE FROM core.domain_intents
            WHERE organization_id = '{SYSTEM_ORG_ID}'
            AND domain_key = '{DOMAIN_KEY}'
            AND intent_key = '{intent_key}'
        """)


def _get_account_selection_intents() -> dict:
    """Get account selection intent patterns - same as Org 1."""
    return {
        "account_selection_existing": {
            "name": "Seleccion Cuenta Existente",
            "description": "Usuario selecciona usar su cuenta existente (opcion 1)",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 100,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                # Number selection
                {"pattern": "1", "pattern_type": "exact"},
                {"pattern": "uno", "pattern_type": "exact"},
                # Verification keywords
                {"pattern": "verificar", "pattern_type": "contains"},
                {"pattern": "mi cuenta", "pattern_type": "contains"},
                {"pattern": "cuenta existente", "pattern_type": "contains"},
                {"pattern": "existente", "pattern_type": "exact"},
                # Position indicators
                {"pattern": "la primera", "pattern_type": "contains"},
                {"pattern": "el primero", "pattern_type": "contains"},
                {"pattern": "primera opcion", "pattern_type": "contains"},
                {"pattern": "primera opcion", "pattern_type": "contains"},
                {"pattern": "opcion 1", "pattern_type": "contains"},
                {"pattern": "opcion 1", "pattern_type": "contains"},
                # Direct selection
                {"pattern": "esa", "pattern_type": "exact"},
                {"pattern": "esa cuenta", "pattern_type": "contains"},
                {"pattern": "usar esa", "pattern_type": "contains"},
                {"pattern": "quiero esa", "pattern_type": "contains"},
            ],
            "keywords": [],
        },
        "account_selection_new": {
            "name": "Seleccion Nueva Cuenta",
            "description": "Usuario quiere usar/crear una cuenta diferente",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 100,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                # Keywords for new account
                {"pattern": "nueva", "pattern_type": "contains"},
                {"pattern": "nuevo", "pattern_type": "contains"},
                {"pattern": "otra", "pattern_type": "contains"},
                {"pattern": "otro", "pattern_type": "contains"},
                {"pattern": "diferente", "pattern_type": "contains"},
                {"pattern": "distinta", "pattern_type": "contains"},
                {"pattern": "distinto", "pattern_type": "contains"},
                # Specific phrases
                {"pattern": "otra cuenta", "pattern_type": "contains"},
                {"pattern": "nueva cuenta", "pattern_type": "contains"},
                {"pattern": "nuevo dni", "pattern_type": "contains"},
                {"pattern": "otra persona", "pattern_type": "contains"},
                {"pattern": "usar otra", "pattern_type": "contains"},
                {"pattern": "crear cuenta", "pattern_type": "contains"},
                {"pattern": "registrar", "pattern_type": "contains"},
                # Last option indicator
                {"pattern": "ultima opcion", "pattern_type": "contains"},
                {"pattern": "ultima opcion", "pattern_type": "contains"},
            ],
            "keywords": [],
        },
        "affirmative_response": {
            "name": "Respuesta Afirmativa",
            "description": "Respuestas afirmativas generales (si, ok, dale, etc.)",
            "weight": 1.0,
            "exact_match": True,
            "is_enabled": True,
            "priority": 90,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                {"pattern": "si", "pattern_type": "exact"},
                {"pattern": "si", "pattern_type": "exact"},
                {"pattern": "s", "pattern_type": "exact"},
                {"pattern": "yes", "pattern_type": "exact"},
                {"pattern": "ok", "pattern_type": "exact"},
                {"pattern": "dale", "pattern_type": "exact"},
                {"pattern": "bueno", "pattern_type": "exact"},
                {"pattern": "claro", "pattern_type": "exact"},
                {"pattern": "listo", "pattern_type": "exact"},
                {"pattern": "perfecto", "pattern_type": "exact"},
                {"pattern": "bien", "pattern_type": "exact"},
                {"pattern": "de acuerdo", "pattern_type": "contains"},
                {"pattern": "esta bien", "pattern_type": "contains"},
                {"pattern": "esta bien", "pattern_type": "contains"},
            ],
            "keywords": [],
        },
    }
