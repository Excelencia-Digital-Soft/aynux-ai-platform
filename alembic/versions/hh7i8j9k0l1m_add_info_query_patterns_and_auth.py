"""Add info_query patterns and auth_required keywords.

Revision ID: hh7i8j9k0l1m
Revises: ee4f5g6h7i8j
Create Date: 2026-01-12

Adds:
1. Additional phrases to info_query intent for complete coverage
2. auth_required keyword to intents that require user identification

This removes hardcoded patterns from PersonResolutionNode and moves them to database.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hh7i8j9k0l1m"
down_revision: Union[str, Sequence[str], None] = "ff5g6h7i8j9k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization UUID for seed data
ORG_1_ID = "00000000-0000-0000-0000-000000000001"
DOMAIN_KEY = "pharmacy"


def upgrade() -> None:
    """Add info_query patterns and auth_required keywords."""
    # Additional info_query phrases (from hardcoded patterns in node.py)
    additional_info_phrases = [
        {"phrase": "info de la farmacia", "match_type": "contains"},
        {"phrase": "informacion de la farmacia", "match_type": "contains"},
        {"phrase": "datos de la farmacia", "match_type": "contains"},
        {"phrase": "contacto de la farmacia", "match_type": "contains"},
        {"phrase": "datos de contacto", "match_type": "contains"},
        {"phrase": "como contactar", "match_type": "contains"},
        {"phrase": "necesito info", "match_type": "contains"},
        {"phrase": "necesito informacion", "match_type": "contains"},
        {"phrase": "quiero info", "match_type": "contains"},
        {"phrase": "quiero informacion", "match_type": "contains"},
        {"phrase": "donde estan", "match_type": "contains"},
        {"phrase": "a que hora", "match_type": "contains"},
        {"phrase": "hora abren", "match_type": "contains"},
        {"phrase": "hora cierran", "match_type": "contains"},
        {"phrase": "cuando abren", "match_type": "contains"},
        {"phrase": "cuando cierran", "match_type": "contains"},
        {"phrase": "numero de telefono", "match_type": "contains"},
        {"phrase": "como llamar", "match_type": "contains"},
        {"phrase": "pagina web", "match_type": "contains"},
        {"phrase": "sitio web", "match_type": "contains"},
    ]

    # Update info_query intent - merge new phrases with existing
    # Using jsonb_set to append to existing phrases array
    for phrase_data in additional_info_phrases:
        phrase = phrase_data["phrase"].replace("'", "''")
        match_type = phrase_data["match_type"]
        op.execute(f"""
            UPDATE core.domain_intents
            SET phrases = phrases || '[{{"phrase": "{phrase}", "match_type": "{match_type}"}}]'::jsonb
            WHERE organization_id = '{ORG_1_ID}'
            AND domain_key = '{DOMAIN_KEY}'
            AND intent_key = 'info_query'
            AND NOT (phrases @> '[{{"phrase": "{phrase}"}}]'::jsonb)
        """)

    # Add auth_required keyword to intents that require user identification
    auth_required_intents = ["debt_query", "invoice", "data_query"]

    for intent_key in auth_required_intents:
        op.execute(f"""
            UPDATE core.domain_intents
            SET keywords = keywords || '["auth_required"]'::jsonb
            WHERE organization_id = '{ORG_1_ID}'
            AND domain_key = '{DOMAIN_KEY}'
            AND intent_key = '{intent_key}'
            AND NOT (keywords @> '["auth_required"]'::jsonb)
        """)


def downgrade() -> None:
    """Remove added patterns and keywords."""
    # Remove auth_required keyword from intents
    auth_required_intents = ["debt_query", "invoice", "data_query"]

    for intent_key in auth_required_intents:
        op.execute(f"""
            UPDATE core.domain_intents
            SET keywords = (
                SELECT jsonb_agg(elem)
                FROM jsonb_array_elements(keywords) AS elem
                WHERE elem::text != '"auth_required"'
            )
            WHERE organization_id = '{ORG_1_ID}'
            AND domain_key = '{DOMAIN_KEY}'
            AND intent_key = '{intent_key}'
        """)

    # Note: We don't remove the additional info_query phrases
    # as they enhance the intent detection without breaking anything
