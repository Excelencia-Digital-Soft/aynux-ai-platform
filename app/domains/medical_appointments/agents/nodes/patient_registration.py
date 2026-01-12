# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Patient registration node.
# ============================================================================
"""Patient Registration Node.

Handles patient registration for new patients not found in the system.
Supports both WhatsApp Flow registration and manual registration.
Refactored with helpers to reduce code duplication (SRP).
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class PatientRegistrationNode(BaseNode):
    """Node for registering new patients."""

    DEFAULT_FLOW_ID = "2244089509373557"
    DEFAULT_SCREEN = "Screen_A"

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process patient registration."""
        phone = state.get("user_phone")
        message = self._get_message(state)

        if flow_data := state.get("registration_flow_data"):
            return await self._process_flow_registration(state, flow_data, phone or "")

        if self._is_registration_data(message):
            return await self._process_manual_registration(state, message, phone or "")

        return await self._show_registration_options(phone)

    # =========================================================================
    # Registration Options
    # =========================================================================

    async def _show_registration_options(self, phone: str | None) -> dict[str, Any]:
        """Show registration options to user."""
        if phone and self._notification:
            if await self._try_send_flow(phone):
                return self._text_response(
                    "Te enviamos un formulario para completar tu registro. "
                    "Por favor, completá tus datos para continuar.",
                    awaiting_registration=True,
                )

        return self._text_response(self._manual_instructions(), awaiting_registration=True)

    async def _try_send_flow(self, phone: str) -> bool:
        """Try to send WhatsApp Flow for registration."""
        try:
            flow_id = self._config.get("registration_flow_id", self.DEFAULT_FLOW_ID)
            screen = self._config.get("registration_screen", self.DEFAULT_SCREEN)

            adapter = await self._notification._get_adapter()  # type: ignore[union-attr, attr-defined]
            await adapter.send_whatsapp_flow(
                msisdn=phone,
                body="Para agendar turnos, necesitamos registrarte en nuestro sistema.",
                flow_id=flow_id,
                flow_cta="Registrarse",
                screen=screen,
                header="Registro de Paciente",
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to send registration flow: {e}")
            return False

    # =========================================================================
    # Flow Registration
    # =========================================================================

    async def _process_flow_registration(
        self, _state: "MedicalAppointmentsState", flow_data: dict[str, Any], phone: str
    ) -> dict[str, Any]:
        """Process registration from WhatsApp Flow."""
        document = flow_data.get("dni", "")
        first_name = flow_data.get("nombre", "")
        last_name = flow_data.get("apellido", "")
        email = flow_data.get("email", "")

        if not document or not first_name:
            return self._text_response(
                "Los datos del formulario están incompletos. " "Por favor, completá todos los campos requeridos.",
                awaiting_registration=True,
            )

        return await self._do_register(
            dni=document,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            full_name=f"{first_name} {last_name}",
        )

    # =========================================================================
    # Manual Registration
    # =========================================================================

    async def _process_manual_registration(
        self, _state: "MedicalAppointmentsState", message: str, phone: str
    ) -> dict[str, Any]:
        """Process manual text-based registration."""
        parts = [p.strip() for p in message.split(",")]
        if len(parts) < 4:
            return self._text_response(
                "Formato incorrecto. Por favor, enviá tus datos así:\n"
                "Nombre Apellido, DNI, Fecha, Teléfono, Email\n\n"
                "Ejemplo: Juan Pérez, 12345678, 15/03/1980, 2615551234, juan@email.com",
                awaiting_registration=True,
            )

        full_name = parts[0]
        document = parts[1].replace(".", "").strip()
        contact_phone = parts[3] if len(parts) > 3 else phone
        email = parts[4] if len(parts) > 4 else ""

        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        if not document.isdigit() or len(document) < 7:
            return self._text_response(
                "El DNI ingresado no es válido. " "Por favor, verificá e intentá nuevamente.",
                awaiting_registration=True,
            )

        return await self._do_register(
            dni=document,
            first_name=first_name,
            last_name=last_name,
            phone=contact_phone,
            email=email,
            full_name=full_name,
        )

    # =========================================================================
    # Core Registration Logic
    # =========================================================================

    async def _do_register(
        self, dni: str, first_name: str, last_name: str, phone: str, email: str, full_name: str
    ) -> dict[str, Any]:
        """Execute patient registration."""
        result = await self._medical.registrar_paciente(
            dni=dni,
            nombre=first_name,
            apellido=last_name,
            telefono=phone,
            email=email,
        )

        if not result.success:
            logger.warning(f"Patient registration failed: {result.error_message}")
            return self._text_response(
                "No pudimos completar tu registro. Por favor, " "contactá a la institución para más ayuda.",
                registration_error=result.error_message,
            )

        patient_data = result.get_dict()
        patient_id = self._extract_patient_id(patient_data)

        if patient_id:
            await self._verify_whatsapp(patient_id)

        return self._success_response(full_name, patient_data, patient_id, dni)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _extract_patient_id(self, data: dict[str, Any]) -> str:
        """Extract patient ID from API response."""
        return str(data.get("idPaciente") or data.get("id") or "")

    def _success_response(
        self, name: str, patient_data: dict[str, Any], patient_id: str, document: str
    ) -> dict[str, Any]:
        """Build successful registration response."""
        return self._text_response(
            f"✅ ¡Registro completado, {name}!\n\n" "Ahora podés agendar tu turno. ¿Qué especialidad necesitás?",
            patient_data=patient_data,
            patient_id=patient_id,
            patient_name=name,
            patient_document=document,
            is_registered=True,
            needs_registration=False,
            awaiting_registration=False,
        )

    async def _verify_whatsapp(self, patient_id: str) -> None:
        """Mark patient as WhatsApp verified."""
        try:
            await self._medical.actualizar_verificacion_whatsapp(
                id_paciente=patient_id,
                verificado=True,
            )
            logger.info(f"Patient {patient_id} marked as WhatsApp verified")
        except Exception as e:
            logger.warning(f"Failed to verify WhatsApp for patient {patient_id}: {e}")

    def _is_registration_data(self, message: str) -> bool:
        """Check if message contains registration data (comma-separated)."""
        return "," in message and len(message.split(",")) >= 3

    def _manual_instructions(self) -> str:
        """Get manual registration instructions text."""
        return (
            "Para registrarte, necesitamos los siguientes datos:\n\n"
            "1. Nombre completo\n"
            "2. DNI (sin puntos)\n"
            "3. Fecha de nacimiento (DD/MM/AAAA)\n"
            "4. Teléfono\n"
            "5. Email (opcional)\n\n"
            "Por favor, enviá tus datos en el siguiente formato:\n"
            "Nombre Apellido, DNI, Fecha, Teléfono, Email\n\n"
            "Ejemplo: Juan Pérez, 12345678, 15/03/1980, 2615551234, juan@email.com"
        )
