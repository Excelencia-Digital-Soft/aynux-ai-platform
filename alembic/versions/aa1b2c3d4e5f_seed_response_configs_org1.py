"""Seed response configs for organization 1.

Revision ID: aa1b2c3d4e5f
Revises: z7h2i34j567k
Create Date: 2026-01-09

Seeds the pharmacy domain response configurations for organization
00000000-0000-0000-0000-000000000001. This ensures the pharmacy agent
can generate responses for this organization.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization UUID for seed data
ORG_1_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Seed response configurations for organization 1."""
    _seed_org1_configs()


def _seed_org1_configs() -> None:
    """Seed response configurations for organization 1."""
    configs = _get_seed_configs()

    for config in configs:
        op.execute(f"""
            INSERT INTO core.response_configs
            (organization_id, domain_key, intent_key, is_critical, task_description, fallback_template_key, display_name)
            VALUES (
                '{ORG_1_ID}',
                'pharmacy',
                '{config['intent_key']}',
                {str(config['is_critical']).lower()},
                '{config['task_description'].replace("'", "''")}',
                '{config['fallback_template_key']}',
                '{config.get('display_name', config['intent_key']).replace("'", "''")}'
            )
            ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING
        """)


def _get_seed_configs() -> list[dict]:
    """Get seed configurations - same as system org."""
    return [
        # ======================================================================
        # CRITICAL INTENTS (is_critical=True) - Always use fixed templates
        # ======================================================================
        {
            "intent_key": "payment_confirmation",
            "is_critical": True,
            "task_description": "Confirma el pago y genera link.",
            "fallback_template_key": "payment_confirmation",
            "display_name": "Confirmación de Pago",
        },
        {
            "intent_key": "payment_link_generated",
            "is_critical": True,
            "task_description": "Muestra el link de pago generado.",
            "fallback_template_key": "payment_link_generated",
            "display_name": "Link de Pago Generado",
        },
        {
            "intent_key": "partial_payment_confirmation",
            "is_critical": True,
            "task_description": "Confirma pago parcial y genera link.",
            "fallback_template_key": "partial_payment_confirmation",
            "display_name": "Confirmación Pago Parcial",
        },
        {
            "intent_key": "system_error",
            "is_critical": True,
            "task_description": "Informa de un error del sistema.",
            "fallback_template_key": "system_error",
            "display_name": "Error del Sistema",
        },
        {
            "intent_key": "plex_unavailable",
            "is_critical": True,
            "task_description": "Informa que Plex no está disponible.",
            "fallback_template_key": "plex_unavailable",
            "display_name": "Plex No Disponible",
        },
        {
            "intent_key": "payment_error",
            "is_critical": True,
            "task_description": "Informa del error en el pago.",
            "fallback_template_key": "payment_error",
            "display_name": "Error de Pago",
        },
        {
            "intent_key": "invalid_dni_format",
            "is_critical": True,
            "task_description": "Informa que el formato de DNI es inválido.",
            "fallback_template_key": "invalid_dni_format",
            "display_name": "DNI Formato Inválido",
        },
        {
            "intent_key": "max_validation_attempts",
            "is_critical": True,
            "task_description": "Informa que se alcanzó el máximo de intentos.",
            "fallback_template_key": "max_validation_attempts",
            "display_name": "Máximo de Intentos",
        },
        {
            "intent_key": "invalid_amount",
            "is_critical": True,
            "task_description": "Informa que el monto es inválido.",
            "fallback_template_key": "invalid_amount",
            "display_name": "Monto Inválido",
        },
        {
            "intent_key": "identity_verified",
            "is_critical": True,
            "task_description": "Confirma que la identidad fue verificada.",
            "fallback_template_key": "identity_verified",
            "display_name": "Identidad Verificada",
        },
        {
            "intent_key": "registration_renewed",
            "is_critical": True,
            "task_description": "Confirma la renovación del registro.",
            "fallback_template_key": "registration_renewed",
            "display_name": "Registro Renovado",
        },
        {
            "intent_key": "debt_display",
            "is_critical": True,
            "task_description": "Muestra la deuda del cliente.",
            "fallback_template_key": "debt_display",
            "display_name": "Mostrar Deuda",
        },
        # ======================================================================
        # GREETING INTENTS
        # ======================================================================
        {
            "intent_key": "greeting",
            "is_critical": False,
            "task_description": "Saluda al cliente y ofrece ayuda.",
            "fallback_template_key": "greeting",
            "display_name": "Saludo",
        },
        {
            "intent_key": "greeting_identified",
            "is_critical": False,
            "task_description": "Saluda al cliente identificado y ofrece ayuda.",
            "fallback_template_key": "greeting_identified",
            "display_name": "Saludo Identificado",
        },
        # ======================================================================
        # DNI REQUEST INTENTS
        # ======================================================================
        {
            "intent_key": "request_dni",
            "is_critical": False,
            "task_description": "Solicita el DNI del cliente para verificar identidad.",
            "fallback_template_key": "request_dni",
            "display_name": "Solicitar DNI",
        },
        {
            "intent_key": "request_dni_welcome",
            "is_critical": False,
            "task_description": "Da la bienvenida y solicita el DNI.",
            "fallback_template_key": "request_dni_welcome",
            "display_name": "Bienvenida + DNI",
        },
        {
            "intent_key": "request_dni_for_other",
            "is_critical": False,
            "task_description": "Solicita el DNI de la otra persona a consultar.",
            "fallback_template_key": "request_dni_for_other",
            "display_name": "DNI de Otra Persona",
        },
        {
            "intent_key": "request_name",
            "is_critical": False,
            "task_description": "Solicita el nombre completo para verificar identidad.",
            "fallback_template_key": "request_name",
            "display_name": "Solicitar Nombre",
        },
        # ======================================================================
        # VALIDATION ERRORS
        # ======================================================================
        {
            "intent_key": "dni_not_found",
            "is_critical": False,
            "task_description": "Informa que el DNI no fue encontrado.",
            "fallback_template_key": "dni_not_found",
            "display_name": "DNI No Encontrado",
        },
        {
            "intent_key": "name_mismatch",
            "is_critical": False,
            "task_description": "Informa que el nombre no coincide y pide que intente de nuevo.",
            "fallback_template_key": "name_mismatch",
            "display_name": "Nombre No Coincide",
        },
        # ======================================================================
        # PERSON RESOLUTION
        # ======================================================================
        {
            "intent_key": "ask_own_or_other",
            "is_critical": False,
            "task_description": "Pregunta si consulta su propia deuda o de otra persona.",
            "fallback_template_key": "ask_own_or_other",
            "display_name": "Propia o Tercero",
        },
        {
            "intent_key": "ambiguous_own_other",
            "is_critical": False,
            "task_description": "Pide clarificación sobre propia o otra persona.",
            "fallback_template_key": "ambiguous_own_other",
            "display_name": "Clarificar Persona",
        },
        {
            "intent_key": "proceed_with_customer",
            "is_critical": False,
            "task_description": "Confirma el cliente y procede a consultar deuda.",
            "fallback_template_key": "proceed_with_customer",
            "display_name": "Proceder con Cliente",
        },
        {
            "intent_key": "no_phone_error",
            "is_critical": False,
            "task_description": "Informa que no se pudo identificar el teléfono.",
            "fallback_template_key": "no_phone_error",
            "display_name": "Error Teléfono",
        },
        {
            "intent_key": "no_pharmacy_error",
            "is_critical": False,
            "task_description": "Informa que no se pudo identificar la farmacia.",
            "fallback_template_key": "no_pharmacy_error",
            "display_name": "Error Farmacia",
        },
        # ======================================================================
        # PERSON SELECTION
        # ======================================================================
        {
            "intent_key": "person_list",
            "is_critical": False,
            "task_description": "Muestra la lista de personas registradas para seleccionar.",
            "fallback_template_key": "person_list",
            "display_name": "Lista de Personas",
        },
        {
            "intent_key": "add_new_person",
            "is_critical": False,
            "task_description": "Inicia el proceso para registrar una nueva persona.",
            "fallback_template_key": "add_new_person",
            "display_name": "Agregar Persona",
        },
        {
            "intent_key": "selection_confirmed",
            "is_critical": False,
            "task_description": "Confirma la selección y consulta la deuda.",
            "fallback_template_key": "selection_confirmed",
            "display_name": "Selección Confirmada",
        },
        {
            "intent_key": "unclear_selection",
            "is_critical": False,
            "task_description": "Pide clarificación sobre la selección.",
            "fallback_template_key": "unclear_selection",
            "display_name": "Selección No Clara",
        },
        # ======================================================================
        # DEBT QUERIES
        # ======================================================================
        {
            "intent_key": "debt_query",
            "is_critical": False,
            "task_description": "Muestra la deuda del cliente.",
            "fallback_template_key": "debt_query",
            "display_name": "Consulta de Deuda",
        },
        {
            "intent_key": "no_customer",
            "is_critical": False,
            "task_description": "Informa que no se identificó al cliente.",
            "fallback_template_key": "no_customer",
            "display_name": "Sin Cliente",
        },
        {
            "intent_key": "no_debt",
            "is_critical": False,
            "task_description": "Informa que no tiene deuda pendiente.",
            "fallback_template_key": "no_debt",
            "display_name": "Sin Deuda",
        },
        {
            "intent_key": "partial_payment_offer",
            "is_critical": False,
            "task_description": "Ofrece la opción de pago parcial.",
            "fallback_template_key": "partial_payment_offer",
            "display_name": "Oferta Pago Parcial",
        },
        {
            "intent_key": "amount_request",
            "is_critical": False,
            "task_description": "Solicita el monto a pagar.",
            "fallback_template_key": "amount_request",
            "display_name": "Solicitar Monto",
        },
        {
            "intent_key": "invalid_amount_input",
            "is_critical": False,
            "task_description": "Informa que el monto no es válido.",
            "fallback_template_key": "invalid_amount_input",
            "display_name": "Monto Input Inválido",
        },
        {
            "intent_key": "amount_below_minimum",
            "is_critical": False,
            "task_description": "Informa que el monto es menor al mínimo.",
            "fallback_template_key": "amount_below_minimum",
            "display_name": "Monto Bajo Mínimo",
        },
        {
            "intent_key": "amount_above_debt",
            "is_critical": False,
            "task_description": "Informa que el monto es mayor a la deuda.",
            "fallback_template_key": "amount_above_debt",
            "display_name": "Monto Sobre Deuda",
        },
        {
            "intent_key": "payment_confirmed",
            "is_critical": False,
            "task_description": "Confirma el pago y genera link.",
            "fallback_template_key": "payment_confirmed",
            "display_name": "Pago Confirmado",
        },
        {
            "intent_key": "partial_payment_confirmed",
            "is_critical": False,
            "task_description": "Confirma pago parcial y genera link.",
            "fallback_template_key": "partial_payment_confirmed",
            "display_name": "Pago Parcial Confirmado",
        },
        {
            "intent_key": "payment_declined",
            "is_critical": False,
            "task_description": "Informa que el pago fue cancelado.",
            "fallback_template_key": "payment_declined",
            "display_name": "Pago Rechazado",
        },
        {
            "intent_key": "unclear_confirmation",
            "is_critical": False,
            "task_description": "Pide confirmación clara SI o NO.",
            "fallback_template_key": "unclear_confirmation",
            "display_name": "Confirmación No Clara",
        },
        # ======================================================================
        # CONFIRMATION FLOW
        # ======================================================================
        {
            "intent_key": "confirmation_cancelled",
            "is_critical": False,
            "task_description": "Confirma que la operación fue cancelada.",
            "fallback_template_key": "confirmation_cancelled",
            "display_name": "Confirmación Cancelada",
        },
        {
            "intent_key": "request_clear_confirmation",
            "is_critical": False,
            "task_description": "Solicita respuesta clara SI o NO.",
            "fallback_template_key": "request_clear_confirmation",
            "display_name": "Solicitar Confirmación",
        },
        {
            "intent_key": "auto_fetching_debt",
            "is_critical": False,
            "task_description": "Informa que está consultando la deuda.",
            "fallback_template_key": "auto_fetching_debt",
            "display_name": "Consultando Deuda",
        },
        {
            "intent_key": "confirmation_no_customer",
            "is_critical": False,
            "task_description": "Informa que no se identificó al cliente.",
            "fallback_template_key": "confirmation_no_customer",
            "display_name": "Confirmación Sin Cliente",
        },
        {
            "intent_key": "confirmation_error",
            "is_critical": False,
            "task_description": "Informa de un error en la confirmación.",
            "fallback_template_key": "confirmation_error",
            "display_name": "Error Confirmación",
        },
        {
            "intent_key": "debt_confirmed_full",
            "is_critical": False,
            "task_description": "Confirma la deuda y procede a generar link.",
            "fallback_template_key": "debt_confirmed_full",
            "display_name": "Deuda Confirmada Total",
        },
        {
            "intent_key": "debt_confirmed_partial",
            "is_critical": False,
            "task_description": "Confirma pago parcial y procede a generar link.",
            "fallback_template_key": "debt_confirmed_partial",
            "display_name": "Deuda Confirmada Parcial",
        },
        # ======================================================================
        # REGISTRATION FLOW
        # ======================================================================
        {
            "intent_key": "registration_yes_no_validation",
            "is_critical": False,
            "task_description": "Solicita confirmación SI o NO.",
            "fallback_template_key": "registration_yes_no_validation",
            "display_name": "Validación SI/NO",
        },
        {
            "intent_key": "registration_start",
            "is_critical": False,
            "task_description": "Inicia el registro solicitando el nombre.",
            "fallback_template_key": "registration_start",
            "display_name": "Inicio Registro",
        },
        {
            "intent_key": "registration_name_error",
            "is_critical": False,
            "task_description": "Informa que el nombre es inválido.",
            "fallback_template_key": "registration_name_error",
            "display_name": "Error Nombre Registro",
        },
        {
            "intent_key": "registration_document_prompt",
            "is_critical": False,
            "task_description": "Solicita el número de documento.",
            "fallback_template_key": "registration_document_prompt",
            "display_name": "Solicitar Documento",
        },
        {
            "intent_key": "registration_document_error",
            "is_critical": False,
            "task_description": "Informa que el documento es inválido.",
            "fallback_template_key": "registration_document_error",
            "display_name": "Error Documento",
        },
        {
            "intent_key": "registration_confirm_data",
            "is_critical": False,
            "task_description": "Muestra los datos para confirmación.",
            "fallback_template_key": "registration_confirm_data",
            "display_name": "Confirmar Datos",
        },
        {
            "intent_key": "registration_success",
            "is_critical": False,
            "task_description": "Confirma el registro exitoso.",
            "fallback_template_key": "registration_success",
            "display_name": "Registro Exitoso",
        },
        {
            "intent_key": "registration_duplicate_with_name",
            "is_critical": False,
            "task_description": "Informa que el cliente ya existe.",
            "fallback_template_key": "registration_duplicate_with_name",
            "display_name": "Cliente Duplicado",
        },
        {
            "intent_key": "registration_duplicate_no_name",
            "is_critical": False,
            "task_description": "Informa que el documento ya está registrado.",
            "fallback_template_key": "registration_duplicate_no_name",
            "display_name": "Documento Duplicado",
        },
        {
            "intent_key": "registration_not_supported",
            "is_critical": False,
            "task_description": "Informa que el registro no está disponible.",
            "fallback_template_key": "registration_not_supported",
            "display_name": "Registro No Soportado",
        },
        {
            "intent_key": "registration_error",
            "is_critical": False,
            "task_description": "Informa del error en el registro.",
            "fallback_template_key": "registration_error",
            "display_name": "Error Registro",
        },
        {
            "intent_key": "registration_cancelled",
            "is_critical": False,
            "task_description": "Confirma la cancelación del registro.",
            "fallback_template_key": "registration_cancelled",
            "display_name": "Registro Cancelado",
        },
        {
            "intent_key": "registration_exception",
            "is_critical": False,
            "task_description": "Informa del error y sugiere intentar de nuevo.",
            "fallback_template_key": "registration_exception",
            "display_name": "Excepción Registro",
        },
        {
            "intent_key": "registration_offer",
            "is_critical": False,
            "task_description": "Ofrece registrarse como nuevo cliente.",
            "fallback_template_key": "registration_offer",
            "display_name": "Oferta Registro",
        },
        # ======================================================================
        # DATA QUERY
        # ======================================================================
        {
            "intent_key": "data_query_no_data",
            "is_critical": False,
            "task_description": "Informa que no hay datos para la consulta.",
            "fallback_template_key": "data_query_no_data",
            "display_name": "Sin Datos",
        },
        {
            "intent_key": "data_query_analyze",
            "is_critical": False,
            "task_description": "Analiza y responde la pregunta sobre los datos.",
            "fallback_template_key": "data_query_analyze",
            "display_name": "Analizar Datos",
        },
        # ======================================================================
        # INFO QUERY
        # ======================================================================
        {
            "intent_key": "info_query_capability",
            "is_critical": False,
            "task_description": "Explica las capacidades del bot.",
            "fallback_template_key": "info_query_capability",
            "display_name": "Capacidades Bot",
        },
        {
            "intent_key": "info_query_no_info",
            "is_critical": False,
            "task_description": "Informa que no hay información de la farmacia.",
            "fallback_template_key": "info_query_no_info",
            "display_name": "Sin Info Farmacia",
        },
        {
            "intent_key": "info_query_generate",
            "is_critical": False,
            "task_description": "Responde con la información de la farmacia.",
            "fallback_template_key": "info_query_generate",
            "display_name": "Info Farmacia",
        },
        # ======================================================================
        # SUMMARY
        # ======================================================================
        {
            "intent_key": "summary_no_data",
            "is_critical": False,
            "task_description": "Informa que no hay datos para resumir.",
            "fallback_template_key": "summary_no_data",
            "display_name": "Sin Datos Resumen",
        },
        {
            "intent_key": "summary_generate",
            "is_critical": False,
            "task_description": "Genera un resumen de la deuda del cliente.",
            "fallback_template_key": "summary_generate",
            "display_name": "Generar Resumen",
        },
        # ======================================================================
        # DISAMBIGUATION
        # ======================================================================
        {
            "intent_key": "request_dni_disambiguation",
            "is_critical": False,
            "task_description": "Solicita el DNI para desambiguación.",
            "fallback_template_key": "request_dni_disambiguation",
            "display_name": "DNI Desambiguación",
        },
        # ======================================================================
        # IDENTIFICATION
        # ======================================================================
        {
            "intent_key": "out_of_scope_identified",
            "is_critical": False,
            "task_description": "Explica límites y sugiere contactar farmacia.",
            "fallback_template_key": "out_of_scope_identified",
            "display_name": "Fuera Alcance Identificado",
        },
        {
            "intent_key": "out_of_scope_not_identified",
            "is_critical": False,
            "task_description": "Explica límites y ofrece identificarse.",
            "fallback_template_key": "out_of_scope_not_identified",
            "display_name": "Fuera Alcance Sin ID",
        },
        {
            "intent_key": "welcome_message",
            "is_critical": False,
            "task_description": "Da la bienvenida y solicita identificación.",
            "fallback_template_key": "welcome_message",
            "display_name": "Mensaje Bienvenida",
        },
        {
            "intent_key": "invalid_document",
            "is_critical": False,
            "task_description": "Informa que el documento es inválido.",
            "fallback_template_key": "invalid_document",
            "display_name": "Documento Inválido",
        },
        {
            "intent_key": "document_reminder",
            "is_critical": False,
            "task_description": "Recuerda que necesita identificarse primero.",
            "fallback_template_key": "document_reminder",
            "display_name": "Recordatorio Documento",
        },
        # ======================================================================
        # GENERIC
        # ======================================================================
        {
            "intent_key": "farewell",
            "is_critical": False,
            "task_description": "Despídete cordialmente.",
            "fallback_template_key": "farewell",
            "display_name": "Despedida",
        },
        {
            "intent_key": "thanks",
            "is_critical": False,
            "task_description": "Responde al agradecimiento del cliente.",
            "fallback_template_key": "thanks",
            "display_name": "Agradecimiento",
        },
        {
            "intent_key": "cancelled",
            "is_critical": False,
            "task_description": "Confirma la cancelación de la operación.",
            "fallback_template_key": "cancelled",
            "display_name": "Cancelado",
        },
        {
            "intent_key": "processing",
            "is_critical": False,
            "task_description": "Indica que está procesando la solicitud.",
            "fallback_template_key": "processing",
            "display_name": "Procesando",
        },
        {
            "intent_key": "unknown",
            "is_critical": False,
            "task_description": "Indica que no entendiste y ofrece opciones.",
            "fallback_template_key": "unknown_intent",
            "display_name": "Desconocido",
        },
        {
            "intent_key": "out_of_scope",
            "is_critical": False,
            "task_description": "Explica qué puedes hacer y sugiere contactar la farmacia.",
            "fallback_template_key": "out_of_scope",
            "display_name": "Fuera de Alcance",
        },
        {
            "intent_key": "generic_error",
            "is_critical": False,
            "task_description": "Informa de un error y pide que intente de nuevo.",
            "fallback_template_key": "generic_error",
            "display_name": "Error Genérico",
        },
        {
            "intent_key": "max_errors_reached",
            "is_critical": False,
            "task_description": "Informa que hubo muchos errores y sugiere contactar.",
            "fallback_template_key": "max_errors_reached",
            "display_name": "Máximo Errores",
        },
    ]


def downgrade() -> None:
    """Remove response configs for organization 1."""
    op.execute(f"""
        DELETE FROM core.response_configs
        WHERE organization_id = '{ORG_1_ID}'
        AND domain_key = 'pharmacy'
    """)
