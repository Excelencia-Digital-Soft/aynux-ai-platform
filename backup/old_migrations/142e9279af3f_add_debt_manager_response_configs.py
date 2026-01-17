"""add_debt_manager_response_configs

Revision ID: 142e9279af3f
Revises: tt9u0v1w2x3y
Create Date: 2026-01-13 18:25:31.356798

Add response configs for debt_not_authenticated and debt_no_debt intents.
Add payment_amount intent patterns for extracting payment amounts from messages.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "142e9279af3f"
down_revision: Union[str, Sequence[str], None] = "tt9u0v1w2x3y"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System organization UUID
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Add debt manager response configs and payment amount patterns."""
    # Insert response configs for debt manager intents
    op.execute(f"""
        INSERT INTO core.response_configs (
            id, organization_id, domain_key, intent_key, is_critical,
            task_description, fallback_template_key, display_name,
            description, priority, is_enabled, created_at, updated_at
        ) VALUES
        (
            gen_random_uuid(),
            '{SYSTEM_ORG_ID}'::uuid,
            'pharmacy',
            'debt_not_authenticated',
            false,
            'Inform the user they need to authenticate before checking their debt. Request their DNI number in a friendly and professional manner.',
            'identification_not_identified',
            'Debt - Not Authenticated',
            'Response when user tries to check debt but is not authenticated',
            50,
            true,
            NOW(),
            NOW()
        ),
        (
            gen_random_uuid(),
            '{SYSTEM_ORG_ID}'::uuid,
            'pharmacy',
            'debt_no_debt',
            false,
            'Congratulate the customer that they have no pending debts. Be friendly and offer to help with other queries.',
            'debt_no_debt',
            'Debt - No Debt Found',
            'Response when customer has no pending debts',
            50,
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING;
    """)

    # Insert payment_amount intent with regex patterns for amount extraction
    # Using connection.execute() directly to avoid SQLAlchemy parameter parsing of regex patterns
    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO core.domain_intents (
                id, organization_id, domain_key, intent_key, name,
                description, weight, exact_match, is_enabled, priority,
                lemmas, phrases, confirmation_patterns, keywords,
                created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                CAST(:org_id AS uuid),
                'pharmacy',
                'payment_amount',
                'Payment Amount Extraction',
                'Regex patterns for extracting payment amounts from user messages',
                1.0,
                false,
                true,
                50,
                '[]'::jsonb,
                CAST(:phrases AS jsonb),
                '[]'::jsonb,
                '["pagar", "pago", "monto", "pesos"]'::jsonb,
                NOW(),
                NOW()
            )
            ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING;
            """
        ),
        {
            "org_id": SYSTEM_ORG_ID,
            "phrases": """[
                {"phrase": "pagar\\\\s*\\\\$?\\\\s*(\\\\d+)", "match_type": "regex"},
                {"phrase": "(\\\\d+)\\\\s*(?:pesos?|pe)", "match_type": "regex"},
                {"phrase": "\\\\$\\\\s*(\\\\d+)", "match_type": "regex"},
                {"phrase": "monto\\\\s*(?:de\\\\s*)?\\\\s*(\\\\d+)", "match_type": "regex"}
            ]""",
        },
    )


def downgrade() -> None:
    """Remove debt manager response configs and payment amount patterns."""
    # Remove response configs
    op.execute(f"""
        DELETE FROM core.response_configs
        WHERE organization_id = '{SYSTEM_ORG_ID}'::uuid
        AND domain_key = 'pharmacy'
        AND intent_key IN ('debt_not_authenticated', 'debt_no_debt');
    """)

    # Remove payment_amount intent
    op.execute(f"""
        DELETE FROM core.domain_intents
        WHERE organization_id = '{SYSTEM_ORG_ID}'::uuid
        AND domain_key = 'pharmacy'
        AND intent_key = 'payment_amount';
    """)
