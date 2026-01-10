# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Specialty selection node.
# ============================================================================
"""Specialty Selection Node.

Handles the selection of medical specialties for appointment booking.
"""

import logging
from typing import TYPE_CHECKING, Any

from ...application.utils import ExternalFieldMapper, ResponseExtractor
from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class SpecialtySelectionNode(BaseNode):
    """Node for handling specialty selection.

    Displays available specialties and processes user selection
    to move to provider selection.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process specialty selection.

        Args:
            state: Current state.

        Returns:
            State updates with selected specialty or specialty list.
        """
        phone = state.get("user_phone")
        specialties = state.get("specialties_list", [])
        selection = self._get_selection(state)

        # If we have a selection, process it
        if selection is not None and specialties:
            return await self._process_selection(state, selection, specialties, phone)

        # Check if we need to load specialties
        if not specialties:
            specialties = await self._load_specialties()
            if not specialties:
                return self._text_response(
                    "No hay especialidades disponibles en este momento. " "Por favor, contactá a la institución."
                )

        # Show specialties list
        return await self._show_specialties(state, specialties, phone)

    async def _load_specialties(self) -> list[dict[str, Any]]:
        """Load specialties from external system."""
        result = await self._medical.obtener_especialidades_bot()

        if not result.success:
            logger.warning(f"Failed to load specialties: {result.error_message}")
            return []

        # Use ResponseExtractor for consistent parsing
        return ResponseExtractor.extract_items(result.data, "especialidades", "items", "datos")

    async def _process_selection(
        self,
        state: "MedicalAppointmentsState",
        selection: int,
        specialties: list[dict[str, Any]],
        phone: str | None,
    ) -> dict[str, Any]:
        """Process specialty selection."""
        if not 0 <= selection < len(specialties):
            return self._text_response(
                f"Opción inválida. Por favor, seleccioná un número del 1 al {len(specialties)}.",
                specialties_list=specialties,
            )

        specialty = specialties[selection]
        # Use ExternalFieldMapper for consistent field extraction
        mapped = ExternalFieldMapper.map_specialty(specialty)
        specialty_id = mapped["specialty_id"]
        specialty_name = mapped["name"]

        # Load providers for selected specialty
        providers = await self._load_providers(specialty_id)

        if not providers:
            return self._text_response(
                f"No hay profesionales disponibles para {specialty_name}. " "Por favor, elegí otra especialidad.",
                specialties_list=specialties,
            )

        # Send interactive list if available
        if phone and self._notification:
            await self._send_interactive_list(
                phone=phone,
                title=f"Profesionales disponibles en {specialty_name}:",
                items=providers,
                button_text="Ver profesionales",
            )

        # Build text response
        response = f"Especialidad: {specialty_name}\n\nProfesionales disponibles:\n\n"
        for i, prov in enumerate(providers[:10], 1):
            name = prov.get("nombreCompleto") or prov.get("nombre") or f"Profesional {i}"
            response += f"{i}. {name}\n"

        return self._text_response(
            response,
            selected_specialty=specialty_id,
            selected_specialty_name=specialty_name,
            providers_list=providers,
        )

    async def _load_providers(self, specialty_id: str) -> list[dict[str, Any]]:
        """Load providers for a specialty."""
        result = await self._medical.obtener_prestadores(specialty_id)

        if not result.success:
            logger.warning(f"Failed to load providers: {result.error_message}")
            return []

        # Use ResponseExtractor for consistent parsing
        return ResponseExtractor.extract_items(result.data, "prestadores", "items", "datos")

    async def _show_specialties(
        self,
        state: "MedicalAppointmentsState",
        specialties: list[dict[str, Any]],
        phone: str | None,
    ) -> dict[str, Any]:
        """Show specialties list."""
        # Send interactive list if available
        if phone and self._notification:
            await self._send_interactive_list(
                phone=phone,
                title="Seleccioná la especialidad para tu turno:",
                items=specialties,
                button_text="Ver especialidades",
            )

        return self._list_response(
            title="Seleccioná la especialidad:",
            items=specialties,
            item_key="nombre",
            prompt="Ingresá el número de la especialidad:",
            specialties_list=specialties,
        )
