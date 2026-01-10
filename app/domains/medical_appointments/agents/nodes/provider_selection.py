# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Provider selection node.
# ============================================================================
"""Provider Selection Node.

Handles the selection of medical providers (doctors) for appointment booking.
"""

import logging
from typing import TYPE_CHECKING, Any

from ...application.utils import ExternalFieldMapper, ResponseExtractor
from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class ProviderSelectionNode(BaseNode):
    """Node for handling provider selection.

    Displays available providers and processes user selection
    to move to date selection.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process provider selection.

        Args:
            state: Current state.

        Returns:
            State updates with selected provider or provider list.
        """
        phone = state.get("user_phone")
        providers = state.get("providers_list", [])
        selection = self._get_selection(state)

        # If we have a selection, process it
        if selection is not None and providers:
            return await self._process_selection(state, selection, providers, phone)

        # Show providers list
        if not providers:
            return self._text_response("No hay profesionales disponibles. " "Por favor, seleccioná otra especialidad.")

        return await self._show_providers(state, providers, phone)

    async def _process_selection(
        self,
        state: "MedicalAppointmentsState",
        selection: int,
        providers: list[dict[str, Any]],
        phone: str | None,
    ) -> dict[str, Any]:
        """Process provider selection."""
        if not 0 <= selection < len(providers):
            return self._text_response(
                f"Opción inválida. Por favor, seleccioná un número del 1 al {len(providers)}.",
                providers_list=providers,
            )

        provider = providers[selection]
        # Use ExternalFieldMapper for consistent field extraction
        mapped = ExternalFieldMapper.map_provider(provider)
        provider_id = mapped["provider_id"]
        provider_name = mapped["full_name"] or mapped["first_name"]

        # Load available dates
        specialty_id = self._get_specialty_id(state)
        dates = await self._load_dates(provider_id, specialty_id)

        if not dates:
            return self._text_response(
                f"No hay fechas disponibles para {provider_name}. " "Por favor, elegí otro profesional.",
                providers_list=providers,
            )

        # Send interactive list if available
        if phone and self._notification:
            date_items = [{"id": d, "nombre": d} for d in dates[:10]]
            await self._send_interactive_list(
                phone=phone,
                title=f"Fechas disponibles con {provider_name}:",
                items=date_items,
                button_text="Ver fechas",
            )

        # Build text response
        response = f"Profesional: {provider_name}\n\nFechas disponibles:\n\n"
        for i, date in enumerate(dates[:10], 1):
            response += f"{i}. {date}\n"

        return self._text_response(
            response,
            selected_provider=provider,
            selected_provider_id=provider_id,
            selected_provider_name=provider_name,
            available_dates=dates,
        )

    async def _load_dates(self, provider_id: str, specialty_id: str) -> list[str]:
        """Load available dates for a provider."""
        result = await self._medical.obtener_dias_disponibles(provider_id, specialty_id)

        if not result.success:
            logger.warning(f"Failed to load dates: {result.error_message}")
            return []

        # Use ResponseExtractor for consistent parsing
        date_items = ResponseExtractor.extract_items(result.data, "dias", "fechas")
        dates: list[str] = []

        for item in date_items:
            fecha = ResponseExtractor.get_field(item, "fecha", "dia")
            if fecha:
                dates.append(fecha)

        return dates

    async def _show_providers(
        self,
        state: "MedicalAppointmentsState",
        providers: list[dict[str, Any]],
        phone: str | None,
    ) -> dict[str, Any]:
        """Show providers list."""
        specialty_name = state.get("selected_specialty_name", "la especialidad")

        # Send interactive list if available
        if phone and self._notification:
            await self._send_interactive_list(
                phone=phone,
                title=f"Profesionales disponibles en {specialty_name}:",
                items=providers,
                button_text="Ver profesionales",
            )

        return self._list_response(
            title=f"Profesionales disponibles en {specialty_name}:",
            items=providers,
            item_key="nombreCompleto",
            prompt="Ingresá el número del profesional:",
            providers_list=providers,
        )
