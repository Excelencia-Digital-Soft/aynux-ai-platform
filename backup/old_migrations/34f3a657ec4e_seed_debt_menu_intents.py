"""seed_debt_menu_intents

Revision ID: 34f3a657ec4e
Revises: ii8j9k0l1m2n
Create Date: 2026-01-12 19:28:26.743636

Seeds 4 new debt menu intents for DB-driven pattern matching in DebtActionHandler:
- debt_menu_pay_total: Option 1 - Pay full debt
- debt_menu_pay_partial: Option 2 - Pay partial debt
- debt_menu_view_details: Option 3 - View invoice details
- debt_menu_return: Option 4 - Return to main menu

These intents replace hardcoded pattern sets with database-driven confirmation patterns,
following CLAUDE.md guidelines for no hardcoding.
"""
from __future__ import annotations

import json
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '34f3a657ec4e'
down_revision: Union[str, Sequence[str], None] = 'ii8j9k0l1m2n'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System organization ID (used for global intents)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"
DOMAIN_KEY = "pharmacy"

# Debt menu intents to seed
DEBT_MENU_INTENTS = {
    "debt_menu_pay_total": {
        "name": "Debt Menu - Pagar Total",
        "description": "Usuario selecciona opción 1 para pagar deuda total",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "1", "pattern_type": "exact"},
            {"pattern": "1️⃣", "pattern_type": "exact"},
            {"pattern": "uno", "pattern_type": "exact"},
            {"pattern": "total", "pattern_type": "exact"},
            {"pattern": "pagar todo", "pattern_type": "exact"},
            {"pattern": "pagar total", "pattern_type": "exact"},
            {"pattern": "pagar todo", "pattern_type": "contains"},
            {"pattern": "pagar el total", "pattern_type": "contains"},
            {"pattern": "pago total", "pattern_type": "contains"},
            {"pattern": "todo el monto", "pattern_type": "contains"},
            {"pattern": "monto total", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_pay_partial": {
        "name": "Debt Menu - Pagar Parcial",
        "description": "Usuario selecciona opción 2 para pagar deuda parcial",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "2", "pattern_type": "exact"},
            {"pattern": "2️⃣", "pattern_type": "exact"},
            {"pattern": "dos", "pattern_type": "exact"},
            {"pattern": "parcial", "pattern_type": "exact"},
            {"pattern": "pagar parcial", "pattern_type": "exact"},
            {"pattern": "mitad", "pattern_type": "exact"},
            {"pattern": "medio", "pattern_type": "exact"},
            {"pattern": "pago parcial", "pattern_type": "contains"},
            {"pattern": "pagar parte", "pattern_type": "contains"},
            {"pattern": "pagar una parte", "pattern_type": "contains"},
            {"pattern": "pagar la mitad", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_view_details": {
        "name": "Debt Menu - Ver Detalle",
        "description": "Usuario selecciona opción 3 para ver detalle de facturas",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "3", "pattern_type": "exact"},
            {"pattern": "3️⃣", "pattern_type": "exact"},
            {"pattern": "tres", "pattern_type": "exact"},
            {"pattern": "detalle", "pattern_type": "exact"},
            {"pattern": "detalles", "pattern_type": "exact"},
            {"pattern": "facturas", "pattern_type": "exact"},
            {"pattern": "ver detalle", "pattern_type": "exact"},
            {"pattern": "ver detalle", "pattern_type": "contains"},
            {"pattern": "ver detalles", "pattern_type": "contains"},
            {"pattern": "ver facturas", "pattern_type": "contains"},
            {"pattern": "ver comprobantes", "pattern_type": "contains"},
            {"pattern": "detalle de", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_return": {
        "name": "Debt Menu - Volver al Menú",
        "description": "Usuario selecciona opción 4 para volver al menú principal",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "4", "pattern_type": "exact"},
            {"pattern": "4️⃣", "pattern_type": "exact"},
            {"pattern": "cuatro", "pattern_type": "exact"},
            {"pattern": "menu", "pattern_type": "exact"},
            {"pattern": "menú", "pattern_type": "exact"},
            {"pattern": "volver", "pattern_type": "exact"},
            {"pattern": "salir", "pattern_type": "exact"},
            {"pattern": "atras", "pattern_type": "exact"},
            {"pattern": "atrás", "pattern_type": "exact"},
            {"pattern": "volver al menu", "pattern_type": "contains"},
            {"pattern": "volver al menú", "pattern_type": "contains"},
            {"pattern": "ir al menu", "pattern_type": "contains"},
            {"pattern": "ir al menú", "pattern_type": "contains"},
            {"pattern": "volver atras", "pattern_type": "contains"},
            {"pattern": "volver atrás", "pattern_type": "contains"},
            {"pattern": "menu principal", "pattern_type": "contains"},
            {"pattern": "menú principal", "pattern_type": "contains"},
            {"pattern": "regresar", "pattern_type": "contains"},
            {"pattern": "al menu", "pattern_type": "contains"},
            {"pattern": "al menú", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
}


def upgrade() -> None:
    """Seed debt menu intents for DB-driven pattern matching."""
    connection = op.get_bind()

    for intent_key, data in DEBT_MENU_INTENTS.items():
        # Check if intent already exists
        result = connection.execute(
            sa.text("""
                SELECT id FROM core.domain_intents
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": intent_key,
            }
        )
        existing = result.fetchone()

        if existing:
            # Update existing intent
            connection.execute(
                sa.text("""
                    UPDATE core.domain_intents SET
                        name = :name,
                        description = :description,
                        weight = :weight,
                        exact_match = :exact_match,
                        is_enabled = :is_enabled,
                        priority = :priority,
                        lemmas = :lemmas,
                        phrases = :phrases,
                        confirmation_patterns = :confirmation_patterns,
                        keywords = :keywords,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": existing[0],
                    "name": data["name"],
                    "description": data["description"],
                    "weight": data["weight"],
                    "exact_match": data["exact_match"],
                    "is_enabled": data["is_enabled"],
                    "priority": data["priority"],
                    "lemmas": json.dumps(data["lemmas"]),
                    "phrases": json.dumps(data["phrases"]),
                    "confirmation_patterns": json.dumps(data["confirmation_patterns"]),
                    "keywords": json.dumps(data["keywords"]),
                }
            )
        else:
            # Insert new intent
            connection.execute(
                sa.text("""
                    INSERT INTO core.domain_intents (
                        id, organization_id, domain_key, intent_key,
                        name, description, weight, exact_match, is_enabled, priority,
                        lemmas, phrases, confirmation_patterns, keywords,
                        created_at, updated_at
                    ) VALUES (
                        :id, :org_id, :domain_key, :intent_key,
                        :name, :description, :weight, :exact_match, :is_enabled, :priority,
                        :lemmas, :phrases, :confirmation_patterns, :keywords,
                        NOW(), NOW()
                    )
                """),
                {
                    "id": str(uuid4()),
                    "org_id": SYSTEM_ORG_ID,
                    "domain_key": DOMAIN_KEY,
                    "intent_key": intent_key,
                    "name": data["name"],
                    "description": data["description"],
                    "weight": data["weight"],
                    "exact_match": data["exact_match"],
                    "is_enabled": data["is_enabled"],
                    "priority": data["priority"],
                    "lemmas": json.dumps(data["lemmas"]),
                    "phrases": json.dumps(data["phrases"]),
                    "confirmation_patterns": json.dumps(data["confirmation_patterns"]),
                    "keywords": json.dumps(data["keywords"]),
                }
            )


def downgrade() -> None:
    """Remove debt menu intents."""
    connection = op.get_bind()

    for intent_key in DEBT_MENU_INTENTS.keys():
        connection.execute(
            sa.text("""
                DELETE FROM core.domain_intents
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": intent_key,
            }
        )
