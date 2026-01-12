"""Update identification flow intents for combined DNI+name request.

Revision ID: dd3e4f5g6h7i
Revises: c9k5l67m890p
Create Date: 2026-01-11

Updates identification flow to:
1. Request DNI and name together (reduces steps from 2 to 1)
2. Add account selection flow for returning users with registered accounts
3. Add intent for when only DNI is provided (prompt for name)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd3e4f5g6h7i"
down_revision: Union[str, Sequence[str], None] = "c9k5l67m890p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization UUIDs
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"
ORG_1_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Update identification flow intents."""
    # Update existing request_identifier to ask for DNI + name together
    _update_request_identifier()

    # Add new intents for the improved flow
    _add_new_intents()


def _update_request_identifier() -> None:
    """Update request_identifier to ask for DNI and name together."""
    new_task = (
        "Solicita que ingrese su DNI y nombre completo en un solo mensaje. "
        "Ejemplo: ''12345678 Juan Pérez''. "
        "Explica que necesitas ambos datos para identificarlo."
    )

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        op.execute(f"""
            UPDATE core.response_configs
            SET task_description = '{new_task}'
            WHERE organization_id = '{org_id}'
            AND domain_key = 'pharmacy'
            AND intent_key = 'request_identifier'
        """)


def _add_new_intents() -> None:
    """Add new intents for improved identification flow."""
    new_configs = [
        # Intent when user provides only DNI (needs name too)
        {
            "intent_key": "request_name_verification",
            "is_critical": False,
            "task_description": (
                "El usuario proporcionó solo el DNI pero falta el nombre. "
                "Pide amablemente que ingrese también su nombre completo para completar la verificación."
            ),
            "fallback_template_key": "request_name_verification",
            "display_name": "Solicitar Nombre (Faltante)",
        },
        # Intent for offering existing accounts to returning users
        {
            "intent_key": "offer_existing_accounts",
            "is_critical": False,
            "task_description": (
                "El usuario tiene cuentas validadas anteriormente. "
                "Muestra las opciones disponibles con el NOMBRE de cada persona (NO mostrar DNI por privacidad). "
                "Formato: 1) Nombre Persona 1, 2) Nombre Persona 2, etc. "
                "Incluir opción final para ''Usar otra cuenta'' o ''Cuenta nueva''."
            ),
            "fallback_template_key": "offer_existing_accounts",
            "display_name": "Ofrecer Cuentas Existentes",
        },
        # Intent for invalid account selection
        {
            "intent_key": "invalid_account_selection",
            "is_critical": False,
            "task_description": (
                "El usuario no seleccionó una opción válida de la lista de cuentas. "
                "Pide que elija un número de la lista o ''nueva'' para registrar otra cuenta."
            ),
            "fallback_template_key": "invalid_account_selection",
            "display_name": "Selección de Cuenta Inválida",
        },
        # Intent for invalid identifier format (update message for combined DNI+name)
        {
            "intent_key": "invalid_identifier_format",
            "is_critical": False,
            "task_description": (
                "El formato del identificador no es válido. "
                "Pide que ingrese su DNI (solo números) seguido de su nombre completo. "
                "Ejemplo: ''12345678 Juan Pérez''."
            ),
            "fallback_template_key": "invalid_identifier_format",
            "display_name": "Formato Identificador Inválido",
        },
        # Intent for identifier not found
        {
            "intent_key": "identifier_not_found",
            "is_critical": False,
            "task_description": (
                "No se encontró un cliente con ese DNI en el sistema. "
                "Ofrece opciones: reintentar con otro dato, registrarse como nuevo cliente, "
                "o contactar directamente a la farmacia."
            ),
            "fallback_template_key": "identifier_not_found",
            "display_name": "Identificador No Encontrado",
        },
        # Intent for successful identification
        {
            "intent_key": "identification_success",
            "is_critical": False,
            "task_description": (
                "La identidad fue verificada exitosamente. "
                "Saluda al cliente por su nombre y muestra el menú principal con las opciones disponibles."
            ),
            "fallback_template_key": "identification_success",
            "display_name": "Identificación Exitosa",
        },
    ]

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        for config in new_configs:
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
                ON CONFLICT (organization_id, domain_key, intent_key) DO UPDATE SET
                    task_description = EXCLUDED.task_description,
                    display_name = EXCLUDED.display_name
            """)


def downgrade() -> None:
    """Revert identification flow changes."""
    # Restore original request_identifier task description
    original_task = "Solicita DNI, número de cliente o CUIT/CUIL para identificar al usuario."

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        op.execute(f"""
            UPDATE core.response_configs
            SET task_description = '{original_task}'
            WHERE organization_id = '{org_id}'
            AND domain_key = 'pharmacy'
            AND intent_key = 'request_identifier'
        """)

    # Remove new intents
    new_intent_keys = [
        "request_name_verification",
        "offer_existing_accounts",
        "invalid_account_selection",
        "invalid_identifier_format",
        "identifier_not_found",
        "identification_success",
    ]

    for org_id in [SYSTEM_ORG_ID, ORG_1_ID]:
        for intent_key in new_intent_keys:
            op.execute(f"""
                DELETE FROM core.response_configs
                WHERE organization_id = '{org_id}'
                AND domain_key = 'pharmacy'
                AND intent_key = '{intent_key}'
            """)
