# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: SOAP method registry for OCP compliance.
# ============================================================================
"""SOAP Method Registry.

Extensible registry for SOAP method configurations.
Allows adding new methods without modifying the client class (OCP).

Usage:
    registry = MethodRegistry()
    registry.register("buscar_paciente", "BuscarPacienteDNI", ["dni"])
    config = registry.get("buscar_paciente")
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MethodConfig:
    """Configuration for a SOAP method.

    Attributes:
        soap_action: SOAP method name (e.g., "BuscarPacienteDNI").
        params: List of parameter names in order.
        include_institution: Whether to auto-include idInstitucion.
        param_transformer: Optional function to transform params before call.
    """

    soap_action: str
    params: list[str] = field(default_factory=list)
    include_institution: bool = True
    param_transformer: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def build_params(
        self,
        institution_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build SOAP parameters from kwargs.

        Args:
            institution_id: Institution ID to include if needed.
            **kwargs: Method arguments.

        Returns:
            Dictionary of SOAP parameters.
        """
        params: dict[str, Any] = {}

        # Map kwargs to SOAP params
        for param_name in self.params:
            if param_name in kwargs:
                params[param_name] = kwargs[param_name]

        # Add institution ID if configured
        if self.include_institution:
            params["idInstitucion"] = institution_id

        # Apply custom transformation if provided
        if self.param_transformer:
            params = self.param_transformer(params)

        return params


class MethodRegistry:
    """Registry of SOAP method configurations.

    Provides OCP-compliant method registration. New methods can be
    added without modifying the client class.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._methods: dict[str, MethodConfig] = {}

    def register(
        self,
        name: str,
        soap_action: str,
        params: list[str] | None = None,
        include_institution: bool = True,
        param_transformer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> "MethodRegistry":
        """Register a SOAP method.

        Args:
            name: Internal method name (e.g., "buscar_paciente_dni").
            soap_action: SOAP action name (e.g., "BuscarPacienteDNI").
            params: List of parameter names.
            include_institution: Whether to include institution ID.
            param_transformer: Optional param transformer function.

        Returns:
            Self for method chaining.
        """
        self._methods[name] = MethodConfig(
            soap_action=soap_action,
            params=params or [],
            include_institution=include_institution,
            param_transformer=param_transformer,
        )
        return self

    def get(self, name: str) -> MethodConfig:
        """Get method configuration.

        Args:
            name: Internal method name.

        Returns:
            MethodConfig for the method.

        Raises:
            KeyError: If method not registered.
        """
        if name not in self._methods:
            raise KeyError(f"Method '{name}' not registered in registry")
        return self._methods[name]

    def has(self, name: str) -> bool:
        """Check if method is registered."""
        return name in self._methods

    def list_methods(self) -> list[str]:
        """List all registered method names."""
        return list(self._methods.keys())


def create_default_registry() -> MethodRegistry:
    """Create registry with default HCWeb methods.

    Returns:
        MethodRegistry with all standard HCWeb SOAP methods.
    """
    registry = MethodRegistry()

    # ==========================================================================
    # IPatientManager methods
    # ==========================================================================
    registry.register(
        "buscar_paciente_dni",
        "BuscarPacienteDNI",
        ["dni"],
    )
    registry.register(
        "buscar_paciente_celular",
        "BuscarPacienteCelular",
        ["celular"],
    )
    registry.register(
        "registrar_paciente",
        "GuardarPacienteInstitucion",
        ["dni", "nombre", "apellido", "telefono", "email", "obraSocial"],
    )
    registry.register(
        "actualizar_verificacion_whatsapp",
        "ActualizarVerificacionWhatsapp",
        ["idpaciente", "verificado"],
        include_institution=True,
        param_transformer=lambda p: {**p, "idinstitucion": p.pop("idInstitucion", "")},
    )

    # ==========================================================================
    # IAppointmentManager methods
    # ==========================================================================
    registry.register(
        "crear_turno",
        "CrearTurno",
        ["idPaciente", "idPrestador", "fechaHora"],
    )
    registry.register(
        "confirmar_turno",
        "ModificarTurnoWhatsapp",
        ["idTurno"],
        include_institution=False,
        param_transformer=lambda p: {**p, "anulado": "0", "motivoAnulacion": ""},
    )
    registry.register(
        "cancelar_turno",
        "ModificarTurnoWhatsapp",
        ["idTurno", "motivoAnulacion"],
        include_institution=False,
        param_transformer=lambda p: {**p, "anulado": "1"},
    )
    registry.register(
        "reprogramar_turno",
        "ModificarTurnoWhatsapp",
        ["idTurno", "fechaturno", "frecuencia"],
        include_institution=False,
        param_transformer=lambda p: {
            **p,
            "anulado": "0",
            "tipoTurno": "7",
            "frecuencia": p.get("frecuencia") or "0",
        },
    )
    registry.register(
        "obtener_turnos_paciente",
        "ObtenerTurnosPacientesWhatsapp",
        ["idpaciente"],
        include_institution=True,
        param_transformer=lambda p: {**p, "idinstitucion": p.pop("idInstitucion", "")},
    )
    registry.register(
        "obtener_turno_sugerido",
        "ObtenerTurnoSugerido",
        ["dni"],
    )
    registry.register(
        "crear_turno_whatsapp",
        "NuevoTurnoWhatsapp",
        ["idpaciente", "idprestador", "fechahora", "frecuencia", "especialidad", "celular"],
        include_institution=True,
        param_transformer=lambda p: {
            **p,
            "idinstitucion": p.pop("idInstitucion", ""),
            "frecuencia": p.get("frecuencia") or "0",
        },
    )

    # ==========================================================================
    # IAvailabilityChecker methods
    # ==========================================================================
    registry.register(
        "obtener_especialidades",
        "ObtenerEspecialidades",
        [],
    )
    registry.register(
        "obtener_especialidades_bot",
        "EspecialidadesBot",
        [],
    )
    registry.register(
        "obtener_prestadores",
        "ObtenerPrestadores",
        ["idEspecialidad"],
    )
    registry.register(
        "obtener_dias_disponibles",
        "ObtenerDiasDisponibles",
        ["idPrestador", "idEspecialidad"],
    )
    registry.register(
        "obtener_horarios_disponibles",
        "ObtenerHorariosDisponibles",
        ["idPrestador", "fecha"],
    )
    registry.register(
        "get_proximo_turno_disponible",
        "GetProximoTurnoDisponible",
        ["idPrestador"],
        include_institution=True,
        param_transformer=lambda p: {**p, "idinstitucion": p.pop("idInstitucion", "")},
    )
    registry.register(
        "get_proximo_turno_disponible_especialidad",
        "GetProximoTurnoDisponibleEspecialidad",
        ["IdEspecialidad"],
        include_institution=True,
        param_transformer=lambda p: {**p, "idinstitucion": p.pop("idInstitucion", "")},
    )
    registry.register(
        "get_fechas_disponibles_prestador",
        "ObtenerDiasDisponiblesPrestador",
        ["idPrestador"],
    )
    registry.register(
        "obtener_especialidades_con_prestadores",
        "EspecialidadPrestadores",
        [],
    )
    registry.register(
        "obtener_dias_turno",
        "ObtenerDiasdelTurnoWhatsapp",
        ["idturno"],
        include_institution=False,
    )
    registry.register(
        "obtener_horas_turno",
        "ObtenerHorasdelTurnoWhatsapp",
        ["idturno", "fecha"],
        include_institution=False,
    )

    # ==========================================================================
    # IReminderManager methods
    # ==========================================================================
    registry.register(
        "obtener_turnos_hoy",
        "BuscarTurnosHoy",
        [],
    )
    registry.register(
        "obtener_turnos_manana",
        "BuscarTurnosManana",
        [],
    )
    registry.register(
        "obtener_turnos_para_recordatorio",
        "ObtenerTurnosParaRecordatorio",
        ["diasFaltantes"],
        include_institution=True,
        param_transformer=lambda p: {**p, "idinstitucion": p.pop("idInstitucion", "")},
    )
    registry.register(
        "marcar_recordatorio_enviado",
        "ActualizarTurnosDiasPreviosWhatsapp",
        ["idTurnos", "EsTurnoSemanal"],
        include_institution=False,
    )
    registry.register(
        "actualizar_turnos_recordatorio_enviado",
        "ActualizarTurnosDiasPreviosWhatsapp",
        ["idTurnos", "EsTurnoSemanal"],
        include_institution=False,
    )

    # ==========================================================================
    # IMedicalSystemClient additional methods
    # ==========================================================================
    registry.register(
        "obtener_informacion_institucion",
        "ObtenerInformacionInstitucion",
        [],
    )
    registry.register(
        "obtener_instituciones_activas",
        "ObtenerInstitucionesActivas",
        [],
        include_institution=False,
    )

    return registry


# Default registry singleton
_default_registry: MethodRegistry | None = None


def get_default_registry() -> MethodRegistry:
    """Get the default method registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_registry()
    return _default_registry
