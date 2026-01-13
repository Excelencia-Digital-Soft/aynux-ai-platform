"""Add remaining response configs to Organization 1.

Revision ID: qq6r7s8t9u0v
Revises: pp5q6r7s8t9u
Create Date: 2026-01-12

Adds 3 response configs that are in System Org but missing from Org 1:
- debt_menu_options: Display debt menu with 4 options
- invoice_details_display: Display invoice/debt details
- return_to_menu: Return to main menu confirmation
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "qq6r7s8t9u0v"
down_revision: Union[str, Sequence[str], None] = "pp5q6r7s8t9u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization 1 UUID (Test Pharmacy)
ORG_1_ID = "00000000-0000-0000-0000-000000000001"
DOMAIN_KEY = "pharmacy"

# Missing response configs to add
MISSING_CONFIGS = [
    {
        "intent_key": "debt_menu_options",
        "is_critical": False,
        "task_description": "Muestra el menú de opciones de deuda: 1-Pagar total, 2-Pagar parcial, 3-Ver detalle, 4-Volver.",
        "fallback_template_key": "debt_menu_options",
        "display_name": "Menú Opciones Deuda",
    },
    {
        "intent_key": "invoice_details_display",
        "is_critical": False,
        "task_description": "Muestra el detalle de las facturas y deudas del cliente.",
        "fallback_template_key": "invoice_details_display",
        "display_name": "Detalle de Facturas",
    },
    {
        "intent_key": "return_to_menu",
        "is_critical": False,
        "task_description": "Confirma el regreso al menú principal y muestra las opciones disponibles.",
        "fallback_template_key": "return_to_menu",
        "display_name": "Volver al Menú",
    },
]


def upgrade() -> None:
    """Add remaining response configs to Organization 1."""
    connection = op.get_bind()

    for config in MISSING_CONFIGS:
        # Check if config already exists
        result = connection.execute(
            sa.text("""
                SELECT id FROM core.response_configs
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": ORG_1_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": config["intent_key"],
            },
        )
        existing = result.fetchone()

        if not existing:
            # Insert new config
            connection.execute(
                sa.text("""
                    INSERT INTO core.response_configs (
                        organization_id, domain_key, intent_key,
                        is_critical, task_description, fallback_template_key, display_name,
                        is_enabled, priority, created_at, updated_at
                    ) VALUES (
                        :org_id, :domain_key, :intent_key,
                        :is_critical, :task_description, :fallback_template_key, :display_name,
                        true, 0, NOW(), NOW()
                    )
                """),
                {
                    "org_id": ORG_1_ID,
                    "domain_key": DOMAIN_KEY,
                    "intent_key": config["intent_key"],
                    "is_critical": config["is_critical"],
                    "task_description": config["task_description"],
                    "fallback_template_key": config["fallback_template_key"],
                    "display_name": config["display_name"],
                },
            )


def downgrade() -> None:
    """Remove added response configs from Organization 1."""
    connection = op.get_bind()

    for config in MISSING_CONFIGS:
        connection.execute(
            sa.text("""
                DELETE FROM core.response_configs
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": ORG_1_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": config["intent_key"],
            },
        )
