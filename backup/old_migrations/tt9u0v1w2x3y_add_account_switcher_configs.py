"""Add account switcher configurations.

Revision ID: tt9u0v1w2x3y
Revises: ss8t9u0v1w2x
Create Date: 2026-01-13

Adds configurations for account_switcher_node.py to eliminate hardcoded values:
1. response_configs: Entries for account-related intents
2. domain_intents: Keyword patterns for account selection
3. pharmacy_merchant_configs: name_match_threshold column

This migration moves hardcoded patterns and messages to database configuration.
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "tt9u0v1w2x3y"
down_revision = "ss8t9u0v1w2x"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# System organization UUID (for default configs)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Add account switcher configurations."""
    # 1. Add name_match_threshold column to pharmacy_merchant_configs
    op.add_column(
        "pharmacy_merchant_configs",
        sa.Column(
            "name_match_threshold",
            sa.Numeric(3, 2),
            nullable=True,
            server_default=sa.text("0.70"),
            comment="Minimum score for fuzzy name matching (0.0-1.0, default 0.7)",
        ),
        schema="pharmacy",
    )

    # 2. Insert response_configs for account switcher intents
    # fmt: off
    op.execute(f"""
        INSERT INTO core.response_configs
            (id, organization_id, domain_key, intent_key, is_critical,
             task_description, fallback_template_key, is_enabled)
        VALUES
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_no_accounts', false,
             'Informa que no tiene cuentas registradas', 'no_registered_accounts', true),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_querying_own', false,
             'Confirma consulta de deuda propia', 'querying_own_debt', true),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_own_or_other', false,
             'Pregunta si deuda propia u otra persona', 'own_or_other_prompt', true),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_add_dni_request', false,
             'Solicita DNI para agregar persona', 'add_person_dni_request', true),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_selection_unclear', false,
             'Indica que no se entendió la selección', 'account_selection_unclear', true),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_selection_confirmed', false,
             'Confirma la cuenta seleccionada', 'account_selection_confirmed', true)
        ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING;
    """)
    # fmt: on

    # 3. Insert domain_intents for account switcher keywords
    # fmt: off
    # Lemmas for account_add_new
    add_new_lemmas = '["agregar", "nueva", "nuevo", "otra", "otro", "diferente", "registrar", "no esta", "no está", "ninguno", "ninguna"]'  # noqa: E501
    own_lemmas = '["mi", "mia", "mía", "mío", "propio", "propia", "yo", "mi deuda"]'
    other_lemmas = '["otro", "otra", "alguien", "otra persona", "diferente"]'

    op.execute(f"""
        INSERT INTO core.domain_intents
            (id, organization_id, domain_key, intent_key, name, description,
             weight, exact_match, is_enabled, priority,
             lemmas, phrases, confirmation_patterns, keywords)
        VALUES
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_add_new',
             'Agregar Nueva Persona', 'Keywords para agregar nueva persona',
             1.0, false, true, 50, '{add_new_lemmas}', '[]', '[]', '[]'),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_own_selection',
             'Selección Propia', 'Keywords para consultar deuda propia',
             1.0, false, true, 50, '{own_lemmas}', '[]', '[]', '["1"]'),
            (gen_random_uuid(), '{SYSTEM_ORG_ID}', 'pharmacy', 'account_other_selection',
             'Selección Otra Persona', 'Keywords para consultar deuda de otra persona',
             1.0, false, true, 50, '{other_lemmas}', '[]', '[]', '["2"]')
        ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING;
    """)
    # fmt: on

    # 4. Update existing pharmacy configs with default threshold
    op.execute("""
        UPDATE pharmacy.pharmacy_merchant_configs
        SET name_match_threshold = 0.70
        WHERE name_match_threshold IS NULL;
    """)


def downgrade() -> None:
    """Remove account switcher configurations."""
    # Remove domain_intents
    op.execute(f"""
        DELETE FROM core.domain_intents
        WHERE domain_key = 'pharmacy'
        AND intent_key IN ('account_add_new', 'account_own_selection', 'account_other_selection')
        AND organization_id = '{SYSTEM_ORG_ID}';
    """)

    # Remove response_configs
    op.execute(f"""
        DELETE FROM core.response_configs
        WHERE domain_key = 'pharmacy'
        AND intent_key IN (
            'account_no_accounts', 'account_querying_own', 'account_own_or_other',
            'account_add_dni_request', 'account_selection_unclear', 'account_selection_confirmed'
        )
        AND organization_id = '{SYSTEM_ORG_ID}';
    """)

    # Drop name_match_threshold column
    op.drop_column("pharmacy_merchant_configs", "name_match_threshold", schema="pharmacy")
