"""Appointment Status Value Object.

Defines the possible states of a medical appointment and their valid transitions.
"""

from enum import Enum


class AppointmentStatus(str, Enum):
    """Estados del turno médico con máquina de estados."""

    PENDING = "pending"  # Pendiente de confirmación
    CONFIRMED = "confirmed"  # Confirmado por el paciente
    CANCELLED = "cancelled"  # Cancelado
    COMPLETED = "completed"  # Completado (atendido)
    NO_SHOW = "no_show"  # No se presentó
    RESCHEDULED = "rescheduled"  # Reprogramado

    @property
    def display_name(self) -> str:
        """Nombre para mostrar en español."""
        names = {
            "pending": "Pendiente",
            "confirmed": "Confirmado",
            "cancelled": "Cancelado",
            "completed": "Completado",
            "no_show": "No se presentó",
            "rescheduled": "Reprogramado",
        }
        return names.get(self.value, self.value)

    @property
    def emoji(self) -> str:
        """Emoji representativo del estado."""
        emojis = {
            "pending": "⏳",
            "confirmed": "✅",
            "cancelled": "❌",
            "completed": "✔️",
            "no_show": "🚫",
            "rescheduled": "🔄",
        }
        return emojis.get(self.value, "")

    def can_transition_to(self, new_status: "AppointmentStatus") -> bool:
        """Validar si la transición de estado es válida.

        State machine:
        - pending -> confirmed, cancelled, rescheduled
        - confirmed -> completed, cancelled, no_show, rescheduled
        - cancelled -> (final state)
        - completed -> (final state)
        - no_show -> (final state)
        - rescheduled -> pending, confirmed, cancelled
        """
        transitions: dict[str, list[str]] = {
            "pending": ["confirmed", "cancelled", "rescheduled"],
            "confirmed": ["completed", "cancelled", "no_show", "rescheduled"],
            "cancelled": [],  # Estado final
            "completed": [],  # Estado final
            "no_show": [],  # Estado final
            "rescheduled": ["pending", "confirmed", "cancelled"],
        }
        return new_status.value in transitions.get(self.value, [])

    def is_active(self) -> bool:
        """¿El turno está activo (puede ser atendido)?"""
        return self.value in ["pending", "confirmed", "rescheduled"]

    def is_final(self) -> bool:
        """¿Es un estado final (no permite más transiciones)?"""
        return self.value in ["cancelled", "completed", "no_show"]

    def requires_reminder(self) -> bool:
        """¿Requiere recordatorio al paciente?"""
        return self.value in ["pending", "confirmed"]

    def allows_cancellation(self) -> bool:
        """¿Se puede cancelar desde este estado?"""
        return self.can_transition_to(AppointmentStatus.CANCELLED)
