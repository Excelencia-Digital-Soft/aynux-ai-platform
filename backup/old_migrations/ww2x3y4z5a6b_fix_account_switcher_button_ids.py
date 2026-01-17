"""Fix account switcher button IDs in domain_intents.

Revision ID: ww2x3y4z5a6b
Revises: vv1w2x3y4z5a
Create Date: 2026-01-14

Adds button IDs to domain_intents keywords so KeywordMatcher can match
WhatsApp button responses (btn_own_debt, btn_other_debt) for the
account own/other selection flow.

This fixes the infinite loop when user clicks "Mi deuda" or "Otra persona"
buttons in the account switcher flow.
"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision = "ww2x3y4z5a6b"
down_revision = "vv1w2x3y4z5a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add button IDs to account selection domain_intents keywords."""
    # Add btn_own_debt to account_own_selection keywords (all organizations)
    op.execute("""
        UPDATE core.domain_intents
        SET keywords = COALESCE(keywords, '[]'::jsonb) || '["btn_own_debt"]'::jsonb
        WHERE domain_key = 'pharmacy'
          AND intent_key = 'account_own_selection'
          AND NOT (COALESCE(keywords, '[]'::jsonb) @> '["btn_own_debt"]'::jsonb);
    """)

    # Add btn_other_debt to account_other_selection keywords (all organizations)
    op.execute("""
        UPDATE core.domain_intents
        SET keywords = COALESCE(keywords, '[]'::jsonb) || '["btn_other_debt"]'::jsonb
        WHERE domain_key = 'pharmacy'
          AND intent_key = 'account_other_selection'
          AND NOT (COALESCE(keywords, '[]'::jsonb) @> '["btn_other_debt"]'::jsonb);
    """)

    # Copy intents from system org to all pharmacy orgs that don't have them
    op.execute("""
        INSERT INTO core.domain_intents
            (id, organization_id, domain_key, intent_key, name, description,
             weight, exact_match, is_enabled, priority,
             lemmas, phrases, confirmation_patterns, keywords)
        SELECT
            gen_random_uuid(),
            o.id,
            di.domain_key, di.intent_key, di.name, di.description,
            di.weight, di.exact_match, di.is_enabled, di.priority,
            di.lemmas, di.phrases, di.confirmation_patterns, di.keywords
        FROM core.domain_intents di
        CROSS JOIN core.organizations o
        WHERE di.organization_id = '00000000-0000-0000-0000-000000000000'
          AND di.domain_key = 'pharmacy'
          AND di.intent_key IN ('account_own_selection', 'account_other_selection', 'account_add_new')
          AND o.id != '00000000-0000-0000-0000-000000000000'
          AND NOT EXISTS (
              SELECT 1 FROM core.domain_intents existing
              WHERE existing.organization_id = o.id
                AND existing.domain_key = di.domain_key
                AND existing.intent_key = di.intent_key
          )
        ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING;
    """)

    # Fix: Remove 'otra persona' from aliases of 'otra cuenta' global keyword
    # This was causing conflicts with the own_or_other button selection
    op.execute("""
        UPDATE core.routing_configs
        SET metadata = jsonb_set(
            metadata,
            '{aliases}',
            '["ver otra cuenta", "cambiar cuenta", "cambiar persona"]'::jsonb
        )
        WHERE trigger_value = 'otra cuenta'
          AND config_type = 'global_keyword'
          AND metadata->'aliases' @> '["otra persona"]'::jsonb;
    """)


def downgrade() -> None:
    """Remove button IDs from account selection domain_intents keywords."""
    # Remove btn_own_debt from account_own_selection keywords
    op.execute("""
        UPDATE core.domain_intents
        SET keywords = keywords - 'btn_own_debt'
        WHERE domain_key = 'pharmacy'
          AND intent_key = 'account_own_selection';
    """)

    # Remove btn_other_debt from account_other_selection keywords
    op.execute("""
        UPDATE core.domain_intents
        SET keywords = keywords - 'btn_other_debt'
        WHERE domain_key = 'pharmacy'
          AND intent_key = 'account_other_selection';
    """)
