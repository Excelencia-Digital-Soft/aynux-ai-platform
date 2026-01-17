"""Add missing response configs to Organization 1.

Revision ID: pp5q6r7s8t9u
Revises: oo4p5q6r7s8t
Create Date: 2026-01-12

Adds 10 missing response configs to Test Pharmacy (Org 1) and fixes
3 configs that had incorrect is_critical values.

New configs added:
- welcome_new_user (is_critical=True)
- welcome_with_payment_intent
- explain_identity_verification
- ambiguous_welcome_response (is_critical=True)
- decline_welcome_options
- request_identifier
- invalid_identifier_format (is_critical=True)
- identifier_not_found (is_critical=True)
- request_name_verification
- identification_success

Configs updated (is_critical fix):
- dni_not_found: False -> True
- generic_error: False -> True
- max_errors_reached: False -> True
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "pp5q6r7s8t9u"
down_revision: Union[str, Sequence[str], None] = "oo4p5q6r7s8t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization 1 UUID (Test Pharmacy)
ORG_1_ID = "00000000-0000-0000-0000-000000000001"
DOMAIN_KEY = "pharmacy"

# Missing response configs to add
MISSING_CONFIGS = [
    {
        "intent_key": "welcome_new_user",
        "is_critical": True,
        "task_description": "Muestra mensaje de bienvenida con 3 opciones para usuario nuevo.",
        "fallback_template_key": "welcome_new_user",
        "display_name": "Bienvenida Usuario Nuevo",
    },
    {
        "intent_key": "welcome_with_payment_intent",
        "is_critical": False,
        "task_description": (
            "El usuario quiere pagar {payment_amount}. "
            "Reconoce su intención de pago y ofrece ayuda para completarlo."
        ),
        "fallback_template_key": "welcome_with_payment_intent",
        "display_name": "Bienvenida con Intención de Pago",
    },
    {
        "intent_key": "explain_identity_verification",
        "is_critical": False,
        "task_description": (
            "Explica por qué es necesaria la verificación de identidad "
            "para proteger datos personales."
        ),
        "fallback_template_key": "explain_identity_verification",
        "display_name": "Explicar Verificación",
    },
    {
        "intent_key": "ambiguous_welcome_response",
        "is_critical": True,
        "task_description": "Pide que elija 1, 2 o 3 porque no se reconoció la respuesta.",
        "fallback_template_key": "ambiguous_welcome_response",
        "display_name": "Respuesta Ambigua Bienvenida",
    },
    {
        "intent_key": "decline_welcome_options",
        "is_critical": False,
        "task_description": (
            "El usuario rechazó las opciones de bienvenida. "
            "Ofrece ayuda alternativa sin requerir autenticación."
        ),
        "fallback_template_key": "decline_welcome_options",
        "display_name": "Rechazo Opciones Bienvenida",
    },
    {
        "intent_key": "request_identifier",
        "is_critical": False,
        "task_description": "Solicita DNI, número de cliente o CUIT/CUIL para identificar al usuario.",
        "fallback_template_key": "request_identifier",
        "display_name": "Solicitar Identificador",
    },
    {
        "intent_key": "invalid_identifier_format",
        "is_critical": True,
        "task_description": "Informa que el formato del identificador no es válido.",
        "fallback_template_key": "invalid_identifier_format",
        "display_name": "Formato Identificador Inválido",
    },
    {
        "intent_key": "identifier_not_found",
        "is_critical": True,
        "task_description": "No se encontró cliente con ese dato. Ofrece reintentar o contactar farmacia.",
        "fallback_template_key": "identifier_not_found",
        "display_name": "Identificador No Encontrado",
    },
    {
        "intent_key": "request_name_verification",
        "is_critical": False,
        "task_description": "Pide que ingrese su nombre completo para verificar identidad.",
        "fallback_template_key": "request_name_verification",
        "display_name": "Verificar Nombre",
    },
    {
        "intent_key": "identification_success",
        "is_critical": False,
        "task_description": "Confirma identificación exitosa y muestra menú principal.",
        "fallback_template_key": "identification_success",
        "display_name": "Identificación Exitosa",
    },
]

# Configs to update is_critical to True
IS_CRITICAL_FIXES = ["dni_not_found", "generic_error", "max_errors_reached"]


def upgrade() -> None:
    """Add missing response configs and fix is_critical values."""
    connection = op.get_bind()

    # Add missing configs
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

    # Fix is_critical values
    for intent_key in IS_CRITICAL_FIXES:
        connection.execute(
            sa.text("""
                UPDATE core.response_configs
                SET is_critical = true, updated_at = NOW()
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": ORG_1_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": intent_key,
            },
        )


def downgrade() -> None:
    """Remove added configs and revert is_critical fixes."""
    connection = op.get_bind()

    # Revert is_critical fixes
    for intent_key in IS_CRITICAL_FIXES:
        connection.execute(
            sa.text("""
                UPDATE core.response_configs
                SET is_critical = false, updated_at = NOW()
                WHERE organization_id = :org_id
                AND domain_key = :domain_key
                AND intent_key = :intent_key
            """),
            {
                "org_id": ORG_1_ID,
                "domain_key": DOMAIN_KEY,
                "intent_key": intent_key,
            },
        )

    # Remove added configs
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
