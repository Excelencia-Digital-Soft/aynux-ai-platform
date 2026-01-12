# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Field mapping utility for external API responses
# ============================================================================
"""Field mapping utility for external API responses.

Maps field names from external APIs (HCWeb/SOAP) to internal domain names,
centralizing the fragile fallback patterns found in DTOs.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldMapping:
    """Definition of a field mapping from external to internal.

    Attributes:
        internal_name: The standardized internal field name.
        external_keys: Possible external field names in priority order.
        default: Default value if no external key is found.
        transform: Optional transformation function.
    """

    internal_name: str
    external_keys: tuple[str, ...]
    default: str = ""

    def extract(self, data: dict[str, Any]) -> str:
        """Extract the field value from external data.

        Args:
            data: External API response dictionary.

        Returns:
            The extracted value as string, or default.
        """
        for key in self.external_keys:
            value = data.get(key)
            if value is not None and value != "":
                return str(value)
        return self.default


class ExternalFieldMapper:
    """Maps fields from external API responses to internal format.

    Centralizes field mapping logic that was previously scattered
    across multiple DTOs with fragile fallback chains.

    Example:
        >>> data = {"idPaciente": "123", "dni": "30123456"}
        >>> mapped = ExternalFieldMapper.map_patient(data)
        >>> mapped["patient_id"]
        "123"
    """

    # Patient field mappings
    PATIENT_MAPPINGS: dict[str, FieldMapping] = {
        "patient_id": FieldMapping(
            "patient_id",
            ("idPaciente", "IdPaciente", "id", "ID"),
        ),
        "document": FieldMapping(
            "document",
            ("dni", "documento", "DNI", "Documento", "nroDocumento"),
        ),
        "first_name": FieldMapping(
            "first_name",
            ("nombre", "Nombre", "firstName", "first_name"),
        ),
        "last_name": FieldMapping(
            "last_name",
            ("apellido", "Apellido", "lastName", "last_name"),
        ),
        "full_name": FieldMapping(
            "full_name",
            ("nombreCompleto", "NombreCompleto", "fullName", "full_name"),
        ),
        "phone": FieldMapping(
            "phone",
            ("celular", "telefono", "Celular", "Telefono", "phone"),
        ),
        "email": FieldMapping(
            "email",
            ("email", "Email", "correo", "Correo"),
        ),
        "health_insurance": FieldMapping(
            "health_insurance",
            ("obraSocial", "ObraSocial", "obra_social", "healthInsurance"),
        ),
        "health_insurance_number": FieldMapping(
            "health_insurance_number",
            ("nroObraSocial", "NroObraSocial", "healthInsuranceNumber"),
        ),
    }

    # Provider field mappings
    PROVIDER_MAPPINGS: dict[str, FieldMapping] = {
        "provider_id": FieldMapping(
            "provider_id",
            ("idPrestador", "IdPrestador", "matricula", "Matricula", "id"),
        ),
        "license_number": FieldMapping(
            "license_number",
            ("matricula", "Matricula", "licenseNumber", "license"),
        ),
        "first_name": FieldMapping(
            "first_name",
            ("nombre", "Nombre", "firstName"),
        ),
        "last_name": FieldMapping(
            "last_name",
            ("apellido", "Apellido", "lastName"),
        ),
        "full_name": FieldMapping(
            "full_name",
            ("nombreCompleto", "NombreCompleto", "fullName"),
        ),
        "specialty_code": FieldMapping(
            "specialty_code",
            ("idEspecialidad", "IdEspecialidad", "especialidad", "specialtyCode"),
        ),
        "specialty_name": FieldMapping(
            "specialty_name",
            (
                "nombreEspecialidad",
                "NombreEspecialidad",
                "especialidadNombre",
                "specialtyName",
            ),
        ),
    }

    # Appointment field mappings
    APPOINTMENT_MAPPINGS: dict[str, FieldMapping] = {
        "appointment_id": FieldMapping(
            "appointment_id",
            ("idTurno", "IdTurno", "id", "ID"),
        ),
        "patient_id": FieldMapping(
            "patient_id",
            ("idPaciente", "IdPaciente"),
        ),
        "provider_id": FieldMapping(
            "provider_id",
            ("idPrestador", "IdPrestador", "matricula"),
        ),
        "date": FieldMapping(
            "date",
            ("fecha", "Fecha", "date"),
        ),
        "time": FieldMapping(
            "time",
            ("hora", "Hora", "time"),
        ),
        "status": FieldMapping(
            "status",
            ("estado", "Estado", "status"),
        ),
        "specialty": FieldMapping(
            "specialty",
            ("especialidad", "Especialidad", "specialty"),
        ),
    }

    # Specialty field mappings
    SPECIALTY_MAPPINGS: dict[str, FieldMapping] = {
        "specialty_id": FieldMapping(
            "specialty_id",
            ("idEspecialidad", "IdEspecialidad", "codigo", "id", "ID"),
        ),
        "code": FieldMapping(
            "code",
            ("codigo", "Codigo", "code"),
        ),
        "name": FieldMapping(
            "name",
            ("nombre", "Nombre", "descripcion", "Descripcion", "name"),
        ),
    }

    # Available slot field mappings
    SLOT_MAPPINGS: dict[str, FieldMapping] = {
        "date": FieldMapping(
            "date",
            ("fecha", "Fecha", "date"),
        ),
        "time": FieldMapping(
            "time",
            ("hora", "Hora", "time"),
        ),
        "available": FieldMapping(
            "available",
            ("disponible", "Disponible", "available"),
            default="true",
        ),
    }

    @classmethod
    def _map_with_mappings(
        cls,
        data: dict[str, Any],
        mappings: dict[str, FieldMapping],
    ) -> dict[str, str]:
        """Apply mappings to extract all fields.

        Args:
            data: External API response dictionary.
            mappings: Field mappings to apply.

        Returns:
            Dictionary with internal field names and extracted values.
        """
        return {mapping.internal_name: mapping.extract(data) for mapping in mappings.values()}

    @classmethod
    def map_patient(cls, data: dict[str, Any]) -> dict[str, str]:
        """Map patient data from external API response.

        Args:
            data: External patient data dictionary.

        Returns:
            Dictionary with standardized patient fields.
        """
        return cls._map_with_mappings(data, cls.PATIENT_MAPPINGS)

    @classmethod
    def map_provider(cls, data: dict[str, Any]) -> dict[str, str]:
        """Map provider data from external API response.

        Args:
            data: External provider data dictionary.

        Returns:
            Dictionary with standardized provider fields.
        """
        return cls._map_with_mappings(data, cls.PROVIDER_MAPPINGS)

    @classmethod
    def map_appointment(cls, data: dict[str, Any]) -> dict[str, str]:
        """Map appointment data from external API response.

        Args:
            data: External appointment data dictionary.

        Returns:
            Dictionary with standardized appointment fields.
        """
        return cls._map_with_mappings(data, cls.APPOINTMENT_MAPPINGS)

    @classmethod
    def map_specialty(cls, data: dict[str, Any]) -> dict[str, str]:
        """Map specialty data from external API response.

        Args:
            data: External specialty data dictionary.

        Returns:
            Dictionary with standardized specialty fields.
        """
        return cls._map_with_mappings(data, cls.SPECIALTY_MAPPINGS)

    @classmethod
    def map_slot(cls, data: dict[str, Any]) -> dict[str, str]:
        """Map available slot data from external API response.

        Args:
            data: External slot data dictionary.

        Returns:
            Dictionary with standardized slot fields.
        """
        return cls._map_with_mappings(data, cls.SLOT_MAPPINGS)

    @classmethod
    def get_patient_id(cls, data: dict[str, Any]) -> str:
        """Quick accessor for patient ID.

        Args:
            data: External data dictionary.

        Returns:
            Patient ID as string.
        """
        return cls.PATIENT_MAPPINGS["patient_id"].extract(data)

    @classmethod
    def get_provider_id(cls, data: dict[str, Any]) -> str:
        """Quick accessor for provider ID.

        Args:
            data: External data dictionary.

        Returns:
            Provider ID as string.
        """
        return cls.PROVIDER_MAPPINGS["provider_id"].extract(data)

    @classmethod
    def get_appointment_id(cls, data: dict[str, Any]) -> str:
        """Quick accessor for appointment ID.

        Args:
            data: External data dictionary.

        Returns:
            Appointment ID as string.
        """
        return cls.APPOINTMENT_MAPPINGS["appointment_id"].extract(data)
