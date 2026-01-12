# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Date selection node.
# ============================================================================
"""Date Selection Node.

Handles the selection of appointment dates.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class DateSelectionNode(BaseNode):
    """Node for handling date selection.

    Displays available dates and processes user selection
    to move to time selection.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process date selection.

        Args:
            state: Current state.

        Returns:
            State updates with selected date or date list.
        """
        phone = state.get("user_phone")
        dates = state.get("available_dates", [])
        selection = self._get_selection(state)

        # If we have a selection, process it
        if selection is not None and dates:
            return await self._process_selection(state, selection, dates, phone)

        # Show dates list
        if not dates:
            return self._text_response("No hay fechas disponibles. " "Por favor, seleccioná otro profesional.")

        return await self._show_dates(state, dates, phone)

    async def _process_selection(
        self,
        state: "MedicalAppointmentsState",
        selection: int,
        dates: list[str],
        phone: str | None,
    ) -> dict[str, Any]:
        """Process date selection."""
        if not 0 <= selection < len(dates):
            return self._text_response(
                f"Opción inválida. Por favor, seleccioná un número del 1 al {len(dates)}.",
                available_dates=dates,
            )

        selected_date = dates[selection]
        provider_id = self._get_provider_id(state)

        # Load available times
        times = await self._load_times(provider_id, selected_date)

        if not times:
            return self._text_response(
                f"No hay horarios disponibles para {selected_date}. " "Por favor, elegí otra fecha.",
                available_dates=dates,
            )

        # Send interactive list if available
        if phone and self._notification:
            time_items = [{"id": t, "nombre": t} for t in times[:10]]
            await self._send_interactive_list(
                phone=phone,
                title=f"Horarios disponibles para {selected_date}:",
                items=time_items,
                button_text="Ver horarios",
            )

        # Build text response
        response = f"Fecha: {selected_date}\n\nHorarios disponibles:\n\n"
        for i, time in enumerate(times[:10], 1):
            response += f"{i}. {time}\n"

        return self._text_response(
            response,
            selected_date=selected_date,
            available_times=times,
        )

    async def _load_times(self, provider_id: str, date: str) -> list[str]:
        """Load available times for a date."""
        result = await self._medical.obtener_horarios_disponibles(provider_id, date)

        if not result.success:
            logger.warning(f"Failed to load times: {result.error_message}")
            return []

        data = result.data
        times: list[str] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    times.append(item)
                elif isinstance(item, dict):
                    hora = item.get("hora") or item.get("horario")
                    if hora:
                        times.append(str(hora))
        elif isinstance(data, dict):
            # Handle morning/afternoon split
            morning = data.get("horariosMñn") or data.get("horariosManana") or []
            afternoon = data.get("horariosTar") or data.get("horariosTarde") or []
            horarios = data.get("horarios", [])

            for hora_list in [horarios, morning, afternoon]:
                if isinstance(hora_list, str):
                    times.append(hora_list)
                elif isinstance(hora_list, list):
                    for item in hora_list:
                        if isinstance(item, str):
                            times.append(item)
                        elif isinstance(item, dict):
                            hora = item.get("hora") or item.get("horario")
                            if hora:
                                times.append(str(hora))

        return times

    async def _show_dates(
        self,
        state: "MedicalAppointmentsState",
        dates: list[str],
        phone: str | None,
    ) -> dict[str, Any]:
        """Show dates list."""
        provider_name = state.get("selected_provider_name", "el profesional")

        # Send interactive list if available
        if phone and self._notification:
            date_items = [{"id": d, "nombre": d} for d in dates[:10]]
            await self._send_interactive_list(
                phone=phone,
                title=f"Fechas disponibles con {provider_name}:",
                items=date_items,
                button_text="Ver fechas",
            )

        response = f"Fechas disponibles con {provider_name}:\n\n"
        for i, date in enumerate(dates[:10], 1):
            response += f"{i}. {date}\n"
        response += "\nIngresá el número de la fecha:"

        return self._text_response(response, available_dates=dates)
