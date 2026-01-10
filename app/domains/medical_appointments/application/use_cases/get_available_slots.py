# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for getting available appointment slots.
# ============================================================================
"""Get Available Slots Use Case.

Handles retrieval of available dates, times, and suggested appointments.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import (
    AvailableDateDTO,
    AvailableSlotDTO,
    GetAvailableSlotsRequest,
    GetAvailableSlotsResult,
    ProviderDTO,
    SpecialtyDTO,
    UseCaseResult,
)
from ..utils import ResponseExtractor

if TYPE_CHECKING:
    from ..ports import IAvailabilityChecker

logger = logging.getLogger(__name__)


class GetAvailableSlotsUseCase:
    """Use case for getting available appointment slots.

    Retrieves available dates, times, and suggested appointments
    from the external medical system.
    """

    def __init__(self, availability_checker: "IAvailabilityChecker") -> None:
        """Initialize use case.

        Args:
            availability_checker: Availability checking interface (DIP).
        """
        self._client = availability_checker

    async def execute(self, request: GetAvailableSlotsRequest) -> GetAvailableSlotsResult:
        """Execute the get available slots use case.

        Args:
            request: Request with provider/specialty and optional date.

        Returns:
            GetAvailableSlotsResult with available dates/slots.
        """
        logger.info(f"Getting available slots for provider {request.provider_id}")

        # Get suggested appointment first
        suggested_response = await self._client.get_proximo_turno_disponible(
            id_prestador=request.provider_id,
        )

        suggested_slot = None
        if suggested_response.success and suggested_response.data:
            data = ResponseExtractor.as_dict(suggested_response.data)
            if data:
                suggested_slot = AvailableSlotDTO(
                    date=ResponseExtractor.get_field(data, "fecha"),
                    time=ResponseExtractor.get_field(data, "hora"),
                    provider_id=request.provider_id,
                    provider_name=ResponseExtractor.get_field(data, "prestador", "nombrePrestador"),
                )

        # Get available dates
        dates_response = await self._client.get_fechas_disponibles_prestador(
            id_prestador=request.provider_id,
        )

        dates: list[AvailableDateDTO] = []
        if dates_response.success and dates_response.data:
            # Extract dates list using ResponseExtractor
            raw_dates = ResponseExtractor.extract_items(dates_response.data, "fechas", "items", "datos")

            for date_item in raw_dates:
                dates.append(
                    AvailableDateDTO(
                        date=ResponseExtractor.get_field(date_item, "fecha"),
                        day_name=ResponseExtractor.get_field(date_item, "dia"),
                    )
                )

        # Get time slots if a specific date was requested
        slots: list[AvailableSlotDTO] = []
        if request.target_date:
            date_str = request.target_date.isoformat()
            times_response = await self._client.obtener_horarios_disponibles(
                id_prestador=request.provider_id,
                fecha=date_str,
            )

            if times_response.success and times_response.data:
                times_data = ResponseExtractor.as_dict(times_response.data)
                # Combine morning and afternoon slots
                morning = times_data.get("horariosMñn") or times_data.get("horariosManana") or []
                afternoon = times_data.get("horariosTar") or times_data.get("horariosTarde") or []
                all_times = morning + afternoon if isinstance(morning, list) else []

                for time_str in all_times:
                    if isinstance(time_str, str):
                        slots.append(
                            AvailableSlotDTO(
                                date=date_str,
                                time=time_str,
                                provider_id=request.provider_id,
                            )
                        )

        return GetAvailableSlotsResult(
            success=True,
            dates=dates,
            slots=slots,
            suggested_slot=suggested_slot,
        )

    async def get_suggested_by_specialty(self, specialty_code: str) -> GetAvailableSlotsResult:
        """Get suggested appointment by specialty.

        Args:
            specialty_code: Code of the specialty.

        Returns:
            GetAvailableSlotsResult with suggested slot.
        """
        logger.info(f"Getting suggested slot for specialty {specialty_code}")

        response = await self._client.get_proximo_turno_disponible_especialidad(
            id_especialidad=specialty_code,
        )

        if not response.success:
            return GetAvailableSlotsResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        suggested_slot = None
        if response.data:
            data = ResponseExtractor.as_dict(response.data)
            if data:
                suggested_slot = AvailableSlotDTO(
                    date=ResponseExtractor.get_field(data, "fecha"),
                    time=ResponseExtractor.get_field(data, "hora"),
                    provider_id=ResponseExtractor.get_field(data, "idPrestador", "matricula"),
                    provider_name=ResponseExtractor.get_field(data, "prestador", "nombrePrestador"),
                )

        return GetAvailableSlotsResult(
            success=True,
            suggested_slot=suggested_slot,
        )

    async def get_specialties(self) -> UseCaseResult:
        """Get available specialties.

        Returns:
            UseCaseResult with list of SpecialtyDTO.
        """
        logger.info("Getting available specialties")

        response = await self._client.obtener_especialidades_bot()

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "SPECIALTIES_ERROR",
                message=response.error_message or "Error al obtener especialidades",
            )

        # Use ResponseExtractor for consistent list parsing
        specialty_list = ResponseExtractor.as_list(response.data)
        specialties = [SpecialtyDTO.from_external_data(item) for item in specialty_list]

        return UseCaseResult.ok(data=specialties)

    async def get_providers_by_specialty(self, specialty_code: str) -> UseCaseResult:
        """Get providers by specialty.

        Args:
            specialty_code: Code of the specialty.

        Returns:
            UseCaseResult with list of ProviderDTO.
        """
        logger.info(f"Getting providers for specialty {specialty_code}")

        response = await self._client.obtener_prestadores(id_especialidad=specialty_code)

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "PROVIDERS_ERROR",
                message=response.error_message or "Error al obtener prestadores",
            )

        # Use ResponseExtractor for consistent list parsing
        provider_list = ResponseExtractor.as_list(response.data)
        providers = [ProviderDTO.from_external_data(item) for item in provider_list]

        return UseCaseResult.ok(data=providers)

    async def get_specialties_with_providers(self) -> UseCaseResult:
        """Get specialties with their providers.

        Returns:
            UseCaseResult with specialties and providers data.
        """
        logger.info("Getting specialties with providers")

        response = await self._client.obtener_especialidades_con_prestadores()

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "DATA_ERROR",
                message=response.error_message or "Error al obtener datos",
            )

        return UseCaseResult.ok(data=response.data)
