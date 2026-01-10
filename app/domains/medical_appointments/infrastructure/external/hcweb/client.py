# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: HCWeb SOAP client implementation.
# ============================================================================
"""HCWeb SOAP Client.

Async client for interacting with the HCWeb medical system via SOAP.
Uses MethodRegistry for OCP-compliant method configuration.

Components:
- SoapRequestBuilder: Builds SOAP envelopes
- SoapResponseParser: Parses SOAP responses
- MethodRegistry: Extensible method configuration
- CircuitBreaker: Resilience pattern for API failures
"""

import logging
from typing import Any

import httpx

from ....application.ports import ExternalResponse, IMedicalSystemClient
from .method_registry import MethodRegistry, get_default_registry
from .resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    ValidationError,
    validate_dni,
    validate_id,
    validate_phone,
    validate_required,
)
from .response_parser import SoapResponseParser
from .soap_builder import SoapRequestBuilder

logger = logging.getLogger(__name__)


class HCWebSOAPClient(IMedicalSystemClient):
    """Async SOAP client for HCWeb.

    Implements IMedicalSystemClient interface for the HCWeb system.
    Uses MethodRegistry for extensible method configuration (OCP).
    """

    def __init__(
        self,
        base_url: str,
        institution_id: str,
        timeout: float = 30.0,
        request_builder: SoapRequestBuilder | None = None,
        response_parser: SoapResponseParser | None = None,
        method_registry: MethodRegistry | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ):
        """Initialize SOAP client.

        Args:
            base_url: SOAP service URL.
            institution_id: Institution ID in HCWeb.
            timeout: Request timeout in seconds.
            request_builder: Optional custom request builder.
            response_parser: Optional custom response parser.
            method_registry: Optional custom method registry.
            circuit_breaker_config: Optional circuit breaker configuration.
        """
        self.base_url = base_url
        self.institution_id = institution_id
        self.timeout = timeout

        self._builder = request_builder or SoapRequestBuilder()
        self._parser = response_parser or SoapResponseParser()
        self._registry = method_registry or get_default_registry()
        self._circuit_breaker = CircuitBreaker(circuit_breaker_config)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "text/xml; charset=utf-8", "Accept": "text/xml"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _call(self, method_name: str, **kwargs: Any) -> ExternalResponse:
        """Call a registered SOAP method.

        Args:
            method_name: Registered method name.
            **kwargs: Method parameters.

        Returns:
            ExternalResponse with result or error.
        """
        config = self._registry.get(method_name)
        params = config.build_params(self.institution_id, **kwargs)
        return await self._call_raw(config.soap_action, params)

    async def _call_raw(self, soap_action: str, params: dict[str, Any]) -> ExternalResponse:
        """Call SOAP method with raw parameters.

        Uses circuit breaker to prevent cascading failures when
        the external service is unavailable.

        Args:
            soap_action: SOAP action name.
            params: Pre-built parameters.

        Returns:
            ExternalResponse with result or error.
        """
        try:
            return await self._circuit_breaker.call(
                self._execute_request,
                soap_action,
                params,
            )
        except CircuitOpenError as e:
            logger.warning(f"Circuit breaker open for {soap_action}: {e}")
            return ExternalResponse.error(
                "SERVICE_UNAVAILABLE",
                "El servicio no está disponible temporalmente. Intente nuevamente.",
            )
        except ValidationError as e:
            logger.warning(f"Validation error in {soap_action}: {e}")
            return ExternalResponse.error("VALIDATION_ERROR", e.message)

    async def _execute_request(self, soap_action: str, params: dict[str, Any]) -> ExternalResponse:
        """Execute the actual SOAP request.

        Args:
            soap_action: SOAP action name.
            params: Pre-built parameters.

        Returns:
            ExternalResponse with result or error.

        Raises:
            Exception: On HTTP or request errors (for circuit breaker).
        """
        client = await self._get_client()
        envelope = self._builder.build_envelope(soap_action, params)

        try:
            response = await client.post(
                self.base_url,
                content=envelope,
                headers={"SOAPAction": f"http://tempuri.org/{soap_action}"},
            )
            response.raise_for_status()
            return self._parser.parse(response.text, soap_action)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {soap_action}: {e.response.status_code}")
            # Re-raise to trigger circuit breaker
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error calling {soap_action}: {e}")
            # Re-raise to trigger circuit breaker
            raise

    # =========================================================================
    # IPatientManager implementation
    # =========================================================================

    async def buscar_paciente_dni(self, dni: str) -> ExternalResponse:
        """Search patient by DNI.

        Args:
            dni: Patient's DNI (validated and normalized).

        Returns:
            ExternalResponse with patient data or error.
        """
        try:
            normalized_dni = validate_dni(dni)
        except ValidationError as e:
            return ExternalResponse.error("VALIDATION_ERROR", e.message)

        return await self._call("buscar_paciente_dni", dni=normalized_dni)

    async def buscar_paciente_celular(self, celular: str) -> ExternalResponse:
        """Search patient by phone.

        Args:
            celular: Phone number (validated and normalized).

        Returns:
            ExternalResponse with patient data or error.
        """
        try:
            normalized_phone = validate_phone(celular)
        except ValidationError as e:
            return ExternalResponse.error("VALIDATION_ERROR", e.message)

        return await self._call("buscar_paciente_celular", celular=normalized_phone)

    async def registrar_paciente(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        telefono: str,
        email: str = "",
        obra_social: str = "",
    ) -> ExternalResponse:
        """Register new patient.

        Args:
            dni: Patient's DNI (required).
            nombre: First name (required).
            apellido: Last name (required).
            telefono: Phone number (required).
            email: Email address (optional).
            obra_social: Health insurance (optional).

        Returns:
            ExternalResponse with registration result.
        """
        try:
            normalized_dni = validate_dni(dni)
            validate_required(nombre, "nombre")
            validate_required(apellido, "apellido")
            normalized_phone = validate_phone(telefono)
        except ValidationError as e:
            return ExternalResponse.error("VALIDATION_ERROR", e.message)

        return await self._call(
            "registrar_paciente",
            dni=normalized_dni,
            nombre=nombre.strip(),
            apellido=apellido.strip(),
            telefono=normalized_phone,
            email=email.strip() if email else "",
            obraSocial=obra_social.strip() if obra_social else "",
        )

    async def actualizar_verificacion_whatsapp(
        self,
        id_paciente: str,
        verificado: bool = True,
    ) -> ExternalResponse:
        """Update WhatsApp verification status."""
        return await self._call(
            "actualizar_verificacion_whatsapp",
            idpaciente=id_paciente,
            verificado=verificado,
        )

    # =========================================================================
    # IAppointmentManager implementation
    # =========================================================================

    async def crear_turno(
        self,
        id_paciente: str,
        id_prestador: str,
        fecha_hora: str,
    ) -> ExternalResponse:
        """Create new appointment."""
        return await self._call(
            "crear_turno",
            idPaciente=id_paciente,
            idPrestador=id_prestador,
            fechaHora=fecha_hora,
        )

    async def confirmar_turno(self, id_turno: str) -> ExternalResponse:
        """Confirm appointment."""
        return await self._call("confirmar_turno", idTurno=id_turno)

    async def cancelar_turno(self, id_turno: str, motivo: str = "") -> ExternalResponse:
        """Cancel appointment."""
        return await self._call("cancelar_turno", idTurno=id_turno, motivoAnulacion=motivo)

    async def reprogramar_turno(
        self,
        id_turno: str,
        fecha_hora: str,
        frecuencia: str = "",
    ) -> ExternalResponse:
        """Reschedule appointment."""
        return await self._call(
            "reprogramar_turno",
            idTurno=id_turno,
            fechaturno=fecha_hora,
            frecuencia=frecuencia,
        )

    async def obtener_turnos_paciente(self, id_paciente: str) -> ExternalResponse:
        """Get patient appointments."""
        return await self._call("obtener_turnos_paciente", idpaciente=id_paciente)

    async def obtener_turno_sugerido(self, dni: str) -> ExternalResponse:
        """Get suggested appointment."""
        return await self._call("obtener_turno_sugerido", dni=dni)

    async def crear_turno_whatsapp(
        self,
        id_paciente: str,
        id_prestador: str,
        fecha_hora: str,
        especialidad: str = "",
        celular: str = "",
        frecuencia: str = "",
    ) -> ExternalResponse:
        """Create appointment via WhatsApp.

        Args:
            id_paciente: Patient ID (required).
            id_prestador: Provider/doctor ID (required).
            fecha_hora: Appointment date and time (required).
            especialidad: Specialty code (optional).
            celular: Patient phone (optional).
            frecuencia: Frequency (optional).

        Returns:
            ExternalResponse with created appointment or error.
        """
        try:
            validate_id(id_paciente, "id_paciente")
            validate_id(id_prestador, "id_prestador")
            validate_required(fecha_hora, "fecha_hora")
        except ValidationError as e:
            return ExternalResponse.error("VALIDATION_ERROR", e.message)

        return await self._call(
            "crear_turno_whatsapp",
            idpaciente=id_paciente,
            idprestador=id_prestador,
            fechahora=fecha_hora,
            especialidad=especialidad,
            celular=celular,
            frecuencia=frecuencia,
        )

    # =========================================================================
    # IAvailabilityChecker implementation
    # =========================================================================

    async def obtener_especialidades(self) -> ExternalResponse:
        """Get available specialties."""
        return await self._call("obtener_especialidades")

    async def obtener_especialidades_bot(self) -> ExternalResponse:
        """Get bot specialties."""
        return await self._call("obtener_especialidades_bot")

    async def obtener_prestadores(self, id_especialidad: str) -> ExternalResponse:
        """Get providers for specialty."""
        return await self._call("obtener_prestadores", idEspecialidad=id_especialidad)

    async def obtener_dias_disponibles(
        self,
        id_prestador: str,
        id_especialidad: str,
    ) -> ExternalResponse:
        """Get available days."""
        return await self._call(
            "obtener_dias_disponibles",
            idPrestador=id_prestador,
            idEspecialidad=id_especialidad,
        )

    async def obtener_horarios_disponibles(
        self,
        id_prestador: str,
        fecha: str,
    ) -> ExternalResponse:
        """Get available times."""
        return await self._call(
            "obtener_horarios_disponibles",
            idPrestador=id_prestador,
            fecha=fecha,
        )

    async def get_proximo_turno_disponible(self, id_prestador: str) -> ExternalResponse:
        """Get next available slot."""
        return await self._call("get_proximo_turno_disponible", idPrestador=id_prestador)

    async def get_proximo_turno_disponible_especialidad(
        self,
        id_especialidad: str,
    ) -> ExternalResponse:
        """Get next available slot for specialty."""
        return await self._call(
            "get_proximo_turno_disponible_especialidad",
            IdEspecialidad=id_especialidad,
        )

    async def get_fechas_disponibles_prestador(self, id_prestador: str) -> ExternalResponse:
        """Get available dates for provider."""
        return await self._call("get_fechas_disponibles_prestador", idPrestador=id_prestador)

    async def obtener_especialidades_con_prestadores(self) -> ExternalResponse:
        """Get specialties with providers."""
        return await self._call("obtener_especialidades_con_prestadores")

    async def obtener_dias_turno(self, id_turno: str) -> ExternalResponse:
        """Get available days for rescheduling."""
        return await self._call("obtener_dias_turno", idturno=id_turno)

    async def obtener_horas_turno(self, id_turno: str, fecha: str) -> ExternalResponse:
        """Get available hours for rescheduling."""
        return await self._call("obtener_horas_turno", idturno=id_turno, fecha=fecha)

    # =========================================================================
    # IReminderManager implementation
    # =========================================================================

    async def obtener_turnos_hoy(self) -> ExternalResponse:
        """Get today's appointments."""
        return await self._call("obtener_turnos_hoy")

    async def obtener_turnos_manana(self) -> ExternalResponse:
        """Get tomorrow's appointments."""
        return await self._call("obtener_turnos_manana")

    async def obtener_turnos_para_recordatorio(
        self,
        dias_anticipacion: int = 1,
    ) -> ExternalResponse:
        """Get appointments for reminder."""
        return await self._call(
            "obtener_turnos_para_recordatorio",
            diasFaltantes=str(dias_anticipacion),
        )

    async def marcar_recordatorio_enviado(self, id_turno: str) -> ExternalResponse:
        """Mark reminder as sent."""
        return await self._call(
            "marcar_recordatorio_enviado",
            idTurnos=[int(id_turno)],
            EsTurnoSemanal="false",
        )

    async def actualizar_turnos_recordatorio_enviado(
        self,
        id_turnos: list[int],
        es_turno_semanal: bool = False,
    ) -> ExternalResponse:
        """Mark multiple appointments as reminded."""
        return await self._call(
            "actualizar_turnos_recordatorio_enviado",
            idTurnos=id_turnos,
            EsTurnoSemanal=str(es_turno_semanal).lower(),
        )

    # =========================================================================
    # IMedicalSystemClient additional methods
    # =========================================================================

    async def obtener_informacion_institucion(self) -> ExternalResponse:
        """Get institution information."""
        return await self._call("obtener_informacion_institucion")

    async def obtener_instituciones_activas(self) -> ExternalResponse:
        """Get active institutions."""
        return await self._call("obtener_instituciones_activas")
