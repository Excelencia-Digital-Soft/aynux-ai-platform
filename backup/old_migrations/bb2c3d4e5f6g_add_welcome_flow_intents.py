"""Add welcome flow intents to response configs.

Revision ID: bb2c3d4e5f6g
Revises: aa1b2c3d4e5f
Create Date: 2026-01-10

Adds missing intents for WelcomeFlowHandler:
- welcome_new_user: Welcome message with 3 options for new users
- ambiguous_welcome_response: Clarification when user response is unclear
- request_identifier: Ask for DNI, client number, or CUIT/CUIL
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb2c3d4e5f6g"
down_revision: Union[str, Sequence[str], None] = "e9c2be43fb21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization UUIDs
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"
ORG_1_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Add welcome flow intents to both organizations."""
    configs = _get_welcome_flow_configs()

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        for config in configs:
            op.execute(f"""
                INSERT INTO core.response_configs
                (organization_id, domain_key, intent_key, is_critical, task_description, fallback_template_key, display_name)
                VALUES (
                    '{org_id}',
                    'pharmacy',
                    '{config['intent_key']}',
                    {str(config['is_critical']).lower()},
                    '{config['task_description'].replace("'", "''")}',
                    '{config['fallback_template_key']}',
                    '{config.get('display_name', config['intent_key']).replace("'", "''")}'
                )
                ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING
            """)


def _get_welcome_flow_configs() -> list[dict]:
    """Get welcome flow intent configurations."""
    return [
        {
            "intent_key": "welcome_new_user",
            "is_critical": False,
            "task_description": "Muestra mensaje de bienvenida con 3 opciones: 1) Soy cliente, 2) Quiero registrarme, 3) Solo información.",
            "fallback_template_key": "welcome_new_user",
            "display_name": "Bienvenida Usuario Nuevo",
        },
        {
            "intent_key": "ambiguous_welcome_response",
            "is_critical": False,
            "task_description": "Pide que el usuario elija una de las 3 opciones (1, 2 o 3) cuando la respuesta no es clara.",
            "fallback_template_key": "ambiguous_welcome_response",
            "display_name": "Respuesta Bienvenida Ambigua",
        },
        {
            "intent_key": "request_identifier",
            "is_critical": False,
            "task_description": "Solicita DNI, número de cliente o CUIT/CUIL para identificar al usuario.",
            "fallback_template_key": "request_identifier",
            "display_name": "Solicitar Identificador",
        },
    ]


def downgrade() -> None:
    """Remove welcome flow intents from both organizations."""
    intent_keys = ["welcome_new_user", "ambiguous_welcome_response", "request_identifier"]

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        for intent_key in intent_keys:
            op.execute(f"""
                DELETE FROM core.response_configs
                WHERE organization_id = '{org_id}'
                AND domain_key = 'pharmacy'
                AND intent_key = '{intent_key}'
            """)
