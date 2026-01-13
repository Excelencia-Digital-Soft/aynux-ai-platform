"""
Response Formatter - WhatsApp message formatting with buttons and lists.

This node formats responses for WhatsApp delivery, supporting:
- Text messages
- Interactive Reply Buttons (max 3 buttons)
- Interactive Lists (up to 10 items)

The formatter sets state fields that are read by the WhatsApp sender service
to determine the appropriate message type and structure.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Formats responses for WhatsApp delivery with button/list support.

    This class generates the appropriate response structure based on
    the current state and context. The formatted response is stored
    in state fields that the WhatsApp sender service reads.

    Response Types:
    - text: Simple text message
    - buttons: Up to 3 reply buttons
    - list: Interactive list with up to 10 items
    """

    def format_debt_response(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format debt display with action buttons.

        Shows total debt and provides buttons for:
        - Pay full amount
        - Pay partial amount
        - Switch to different account

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        total = state.get("total_debt") or 0
        customer = state.get("customer_name") or "Cliente"
        pharmacy = state.get("pharmacy_name") or "Farmacia"

        # Build message body
        body = f"*{pharmacy}*\n\n"
        body += "*Resumen de Cuenta*\n\n"
        body += f"Cliente: {customer}\n"
        body += f"Saldo pendiente: ${total:,.2f}\n\n"
        body += "Selecciona una opcion:"

        # Create buttons
        buttons = [
            {"id": "btn_pay_full", "titulo": f"Pagar ${total:,.2f}"},
            {"id": "btn_pay_partial", "titulo": "Pago parcial"},
            {"id": "btn_switch_account", "titulo": "Otra cuenta"},
        ]

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            # Store formatted body for message content
            "_formatted_body": body,
            "_formatted_title": "Consulta de Deuda",
        }

    def format_payment_confirmation(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format payment confirmation with Yes/No buttons.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        amount = state.get("payment_amount") or 0
        total = state.get("total_debt") or 0
        is_partial = state.get("is_partial_payment", False)

        if is_partial:
            remaining = total - amount
            body = "*Confirmar Pago Parcial*\n\n"
            body += f"Monto a pagar: ${amount:,.2f}\n"
            body += f"Saldo restante: ${remaining:,.2f}\n\n"
            body += "Confirmas el pago?"
        else:
            body = "*Confirmar Pago*\n\n"
            body += f"Monto: ${amount:,.2f}\n\n"
            body += "Confirmas el pago?"

        buttons = [
            {"id": "btn_confirm_yes", "titulo": "Si, pagar"},
            {"id": "btn_confirm_no", "titulo": "Cancelar"},
        ]

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": "Confirmacion de Pago",
        }

    def format_payment_link(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format payment link message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        link = state.get("mp_payment_link") or ""
        amount = state.get("payment_amount") or 0

        body = "*Link de Pago*\n\n"
        body += f"Monto: ${amount:,.2f}\n\n"
        body += f"Hace clic aqui para pagar:\n{link}\n\n"
        body += "El link tiene validez de 24 horas."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
        }

    def format_account_selection(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format account selection list.

        Uses WhatsApp Interactive List for multiple accounts.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        accounts = state.get("registered_accounts") or []

        body = "*Selecciona una cuenta*\n\n"
        body += "Toca el boton para ver las opciones disponibles."

        # Build list items (max 10)
        list_items = []
        for acc in accounts[:10]:
            debt = acc.get("debt", 0)
            list_items.append(
                {
                    "id": f"account_{acc.get('id', '')}",
                    "titulo": str(acc.get("name", ""))[:24],  # Max 24 chars for title
                    "descripcion": f"Deuda: ${debt:,.2f}",
                }
            )

        # Add option to add new person
        if len(accounts) < 10:
            list_items.append(
                {
                    "id": "btn_add_new_person",
                    "titulo": "Agregar persona",
                    "descripcion": "Registrar nueva persona",
                }
            )

        return {
            "response_type": "list",
            "response_buttons": None,
            "response_list_items": list_items,
            "_formatted_body": body,
            "_formatted_title": "Cuentas Disponibles",
            "_list_button_text": "Ver cuentas",
        }

    def format_own_or_other(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format own/other debt selection.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        body = "Deseas consultar tu propia deuda o la de otra persona?"

        buttons = [
            {"id": "btn_own_debt", "titulo": "Mi deuda"},
            {"id": "btn_other_debt", "titulo": "Otra persona"},
        ]

        return {
            "response_type": "buttons",
            "response_buttons": buttons,
            "response_list_items": None,
            "_formatted_body": body,
            "_formatted_title": "Consulta de Deuda",
        }

    def format_main_menu(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format main menu message.

        Uses text with numbered options since WhatsApp buttons are limited to 3.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        pharmacy = state.get("pharmacy_name") or "Farmacia"
        customer = state.get("customer_name") or ""

        greeting = f"Hola{' ' + customer if customer else ''}!"

        body = f"*{pharmacy}*\n\n"
        body += f"{greeting}\n\n"
        body += "Como puedo ayudarte hoy?\n\n"
        body += "1. Consultar deuda\n"
        body += "2. Generar link de pago\n"
        body += "3. Historial de pagos\n"
        body += "4. Informacion de la farmacia\n"
        body += "5. Cambiar cuenta\n"
        body += "6. Ayuda\n"
        body += "0. Salir\n\n"
        body += "Responde con el numero de la opcion."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "awaiting_input": "menu_selection",
        }

    def format_no_debt(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format no debt message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        customer = state.get("customer_name") or "tu cuenta"

        body = "*Sin Deuda Pendiente*\n\n"
        body += f"No hay deuda registrada para {customer}.\n\n"
        body += "Si crees que esto es un error, comunicate con la farmacia."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
        }

    def format_error(
        self,
        error_type: str,
        state: "PharmacyStateV2",
    ) -> dict[str, Any]:
        """
        Format error message.

        Args:
            error_type: Type of error (plex_unavailable, payment_error, etc.)
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        error_messages = {
            "plex_unavailable": (
                "*Sistema No Disponible*\n\n"
                "El sistema de consultas no esta disponible en este momento.\n"
                "Por favor intenta mas tarde o comunicate con la farmacia."
            ),
            "payment_error": (
                "*Error de Pago*\n\n"
                "Hubo un problema al procesar tu pago.\n"
                "Por favor intenta nuevamente o comunicate con la farmacia."
            ),
            "generic": ("*Error*\n\n" "Ocurrio un error inesperado.\n" "Por favor intenta nuevamente."),
        }

        body = error_messages.get(error_type, error_messages["generic"])

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "error_count": (state.get("error_count") or 0) + 1,
        }

    def format_farewell(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format farewell message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        pharmacy = state.get("pharmacy_name") or "Farmacia"
        customer = state.get("customer_name") or ""

        body = f"*{pharmacy}*\n\n"
        body += f"Gracias por comunicarte{' ' + customer if customer else ''}!\n\n"
        body += "Que tengas un excelente dia."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "is_complete": True,
        }

    def format_request_dni(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format DNI request message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        body = "Para continuar, necesito verificar tu identidad.\n\n"
        body += "Por favor ingresa tu numero de DNI (solo numeros)."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "awaiting_input": "dni",
        }

    def format_request_name(self, state: "PharmacyStateV2") -> dict[str, Any]:
        """
        Format name request message.

        Args:
            state: Current conversation state

        Returns:
            State updates with formatted response
        """
        body = "Por favor ingresa tu nombre completo para verificar tu identidad."

        return {
            "response_type": "text",
            "response_buttons": None,
            "response_list_items": None,
            "_formatted_body": body,
            "awaiting_input": "name",
        }


# Singleton instance
response_formatter = ResponseFormatter()


# LangGraph node function
async def response_formatter_node(
    state: "PharmacyStateV2",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    LangGraph node function for response formatting.

    This node is called after processing to format the response
    for WhatsApp delivery. It determines the appropriate format
    based on the current state and intent.

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates with response formatting
    """
    intent = state.get("intent")
    has_debt = state.get("has_debt", False)
    is_complete = state.get("is_complete", False)

    # If already complete, format farewell
    if is_complete:
        return response_formatter.format_farewell(state)

    # Format based on intent/context
    if intent == "check_debt" or intent == "debt_query":
        if has_debt:
            return response_formatter.format_debt_response(state)
        else:
            return response_formatter.format_no_debt(state)

    elif intent in ("pay_full", "pay_partial", "payment_link"):
        # Check if we have a payment link
        if state.get("mp_payment_link"):
            return response_formatter.format_payment_link(state)
        elif state.get("awaiting_payment_confirmation"):
            return response_formatter.format_payment_confirmation(state)
        else:
            return response_formatter.format_debt_response(state)

    elif intent == "switch_account":
        if state.get("awaiting_account_selection"):
            return response_formatter.format_account_selection(state)
        else:
            return response_formatter.format_own_or_other(state)

    elif intent == "show_menu":
        return response_formatter.format_main_menu(state)

    elif intent == "farewell":
        return response_formatter.format_farewell(state)

    # Default: show main menu
    return response_formatter.format_main_menu(state)
