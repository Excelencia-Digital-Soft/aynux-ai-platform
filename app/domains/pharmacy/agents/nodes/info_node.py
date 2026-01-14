"""
Info Node - V2 Pharmacy Information Node.

Handles pharmacy information queries.
Uses PharmacyInfoService to load and display pharmacy data.

Uses V2 state fields: pharmacy_id, pharmacy_name, etc.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableConfig

from app.domains.pharmacy.services.pharmacy_info_service import PharmacyInfoService

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


async def info_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Info node - handles pharmacy information queries.

    Displays pharmacy contact info, hours, address, etc.

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates with pharmacy info response
    """
    service = PharmacyInfoService()

    # Get pharmacy ID from state
    pharmacy_id = state.get("pharmacy_id")

    if not pharmacy_id:
        logger.warning("No pharmacy_id in state for info query")
        return _handle_no_pharmacy()

    # Load pharmacy info
    info = await service.get_pharmacy_info(str(pharmacy_id))

    if not info:
        logger.warning(f"Pharmacy info not found: {pharmacy_id}")
        return _handle_info_not_found()

    # Format response
    response_text = _format_pharmacy_info(info)

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "info_node",
        "agent_history": ["info_node"],
        "is_complete": True,
    }


def _format_pharmacy_info(info: dict[str, Any]) -> str:
    """Format pharmacy information for WhatsApp."""
    name = info.get("name", "Farmacia")
    address = info.get("address")
    phone = info.get("phone")
    email = info.get("email")
    website = info.get("website")
    hours = info.get("hours")
    is_24h = info.get("is_24h", False)

    lines = [
        f"💊 *{name}*",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "*Informacion de Contacto*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if address:
        lines.append("📍 *Direccion:*")
        lines.append(f"   {address}")
        lines.append("")

    if phone:
        lines.append("📞 *Telefono:*")
        lines.append(f"   {phone}")
        lines.append("")

    if email:
        lines.append("📧 *Email:*")
        lines.append(f"   {email}")
        lines.append("")

    if website:
        lines.append("🌐 *Web:*")
        lines.append(f"   {website}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("*Horarios de Atencion*")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if is_24h:
        lines.append("⏰ *Abierto las 24 horas*")
    elif hours:
        lines.append(f"⏰ {hours}")
    else:
        lines.append("⏰ Consultar con la farmacia")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("Escribe *MENU* para ver mas opciones.")

    return "\n".join(lines)


def _handle_no_pharmacy() -> dict[str, Any]:
    """Handle missing pharmacy ID."""
    return {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "Disculpa, no se pudo identificar la farmacia.\n\n"
                    "Por favor contacta a soporte si este problema persiste."
                ),
            }
        ],
        "current_node": "info_node",
        "is_complete": True,
    }


def _handle_info_not_found() -> dict[str, Any]:
    """Handle pharmacy info not found."""
    return {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "Disculpa, la informacion de la farmacia no esta disponible.\n\n"
                    "Por favor intenta mas tarde o contacta directamente a la farmacia."
                ),
            }
        ],
        "current_node": "info_node",
        "is_complete": True,
    }


__all__ = ["info_node"]
