"""Medical Specialty Value Object.

Defines medical specialties available in the system.
"""

from enum import Enum


class MedicalSpecialty(str, Enum):
    """Especialidades médicas disponibles."""

    # General
    GENERAL = "general"
    GENERAL_PRACTICE = "medicina_general"

    # Digestive/Gastro (Primary for Patología Digestiva)
    GASTROENTEROLOGY = "gastroenterologia"
    HEPATOLOGY = "hepatologia"
    ENDOSCOPY = "endoscopia"
    COLONOSCOPY = "colonoscopia"
    PROCTOLOGY = "proctologia"

    # Other common specialties
    CARDIOLOGY = "cardiologia"
    DERMATOLOGY = "dermatologia"
    NEUROLOGY = "neurologia"
    OPHTHALMOLOGY = "oftalmologia"
    ORTHOPEDICS = "traumatologia"
    PEDIATRICS = "pediatria"
    GYNECOLOGY = "ginecologia"
    UROLOGY = "urologia"
    PSYCHIATRY = "psiquiatria"
    INTERNAL_MEDICINE = "clinica_medica"

    @property
    def display_name(self) -> str:
        """Nombre para mostrar en español."""
        names = {
            "general": "General",
            "medicina_general": "Medicina General",
            "gastroenterologia": "Gastroenterología",
            "hepatologia": "Hepatología",
            "endoscopia": "Endoscopía",
            "colonoscopia": "Colonoscopía",
            "proctologia": "Proctología",
            "cardiologia": "Cardiología",
            "dermatologia": "Dermatología",
            "neurologia": "Neurología",
            "oftalmologia": "Oftalmología",
            "traumatologia": "Traumatología",
            "pediatria": "Pediatría",
            "ginecologia": "Ginecología",
            "urologia": "Urología",
            "psiquiatria": "Psiquiatría",
            "clinica_medica": "Clínica Médica",
        }
        return names.get(self.value, self.value.replace("_", " ").title())

    @property
    def code(self) -> str:
        """Código corto para la especialidad."""
        codes = {
            "general": "GEN",
            "medicina_general": "MG",
            "gastroenterologia": "GASTRO",
            "hepatologia": "HEPA",
            "endoscopia": "ENDO",
            "colonoscopia": "COLO",
            "proctologia": "PROC",
            "cardiologia": "CARDIO",
            "dermatologia": "DERM",
            "neurologia": "NEURO",
            "oftalmologia": "OFTAL",
            "traumatologia": "TRAUMA",
            "pediatria": "PED",
            "ginecologia": "GIN",
            "urologia": "URO",
            "psiquiatria": "PSIQ",
            "clinica_medica": "CM",
        }
        return codes.get(self.value, self.value[:4].upper())

    def is_digestive_specialty(self) -> bool:
        """¿Es una especialidad del sistema digestivo?"""
        digestive = {
            "gastroenterologia",
            "hepatologia",
            "endoscopia",
            "colonoscopia",
            "proctologia",
        }
        return self.value in digestive

    @classmethod
    def get_digestive_specialties(cls) -> list["MedicalSpecialty"]:
        """Obtener todas las especialidades digestivas."""
        return [s for s in cls if s.is_digestive_specialty()]

    @classmethod
    def from_code(cls, code: str) -> "MedicalSpecialty | None":
        """Obtener especialidad por código."""
        code = code.upper()
        for specialty in cls:
            if specialty.code == code:
                return specialty
        return None
