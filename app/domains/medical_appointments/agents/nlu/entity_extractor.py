# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Entity extraction for medical appointment conversations.
# ============================================================================
"""Medical Entity Extractor.

Extracts relevant entities from user messages in the medical appointments
domain, including specialties, dates, times, and document numbers.

Supported Entities:
    - specialty: Medical specialty mentioned
    - date: Date mentioned (relative or absolute)
    - time: Time preference mentioned
    - provider_name: Doctor/provider name mentioned
    - document: Patient document number (DNI)
    - phone: Phone number mentioned
    - selection: Numeric selection from a list

Usage:
    extractor = MedicalEntityExtractor()
    entities = await extractor.extract("Quiero un turno para cardiología mañana")
    print(entities)  # {"specialty": "cardiología", "date": "mañana"}
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Common medical specialties (Spanish)
MEDICAL_SPECIALTIES = frozenset({
    # Cardiology
    "cardiología", "cardiologia", "cardio", "corazón",
    # General Medicine
    "clínica médica", "clinica medica", "medicina general", "médico general",
    "clinico", "clínico",
    # Gynecology
    "ginecología", "ginecologia", "gineco", "gine",
    # Pediatrics
    "pediatría", "pediatria", "pediatra", "niños",
    # Dermatology
    "dermatología", "dermatologia", "dermato", "piel",
    # Ophthalmology
    "oftalmología", "oftalmologia", "oculista", "ojos",
    # Traumatology
    "traumatología", "traumatologia", "traumato", "huesos",
    # Neurology
    "neurología", "neurologia", "neuro",
    # Gastroenterology
    "gastroenterología", "gastroenterologia", "gastro",
    # Urology
    "urología", "urologia", "urologo",
    # Otorhinolaryngology
    "otorrinolaringología", "otorrino", "garganta", "oído", "nariz",
    # Psychiatry
    "psiquiatría", "psiquiatria", "psiquiatra",
    # Psychology
    "psicología", "psicologia", "psicologo", "psicólogo",
    # Nutrition
    "nutrición", "nutricion", "nutricionista",
    # Odontology
    "odontología", "odontologia", "dentista", "dental",
    # Radiology
    "radiología", "radiologia", "rayos",
    # Laboratory
    "laboratorio", "análisis", "sangre",
    # Speech therapy
    "fonoaudiología", "fonoaudiologia", "fono",
    # Physical therapy
    "kinesiología", "kinesiologia", "kinesio", "fisioterapia",
    # Endocrinology
    "endocrinología", "endocrinologia", "endocrino",
})

# Specialty normalization mapping
SPECIALTY_NORMALIZATION: dict[str, str] = {
    "cardio": "cardiología",
    "corazón": "cardiología",
    "clinico": "clínica médica",
    "clínico": "clínica médica",
    "médico general": "clínica médica",
    "medicina general": "clínica médica",
    "gineco": "ginecología",
    "gine": "ginecología",
    "pediatra": "pediatría",
    "niños": "pediatría",
    "dermato": "dermatología",
    "piel": "dermatología",
    "oculista": "oftalmología",
    "ojos": "oftalmología",
    "traumato": "traumatología",
    "huesos": "traumatología",
    "neuro": "neurología",
    "gastro": "gastroenterología",
    "urologo": "urología",
    "otorrino": "otorrinolaringología",
    "garganta": "otorrinolaringología",
    "oído": "otorrinolaringología",
    "nariz": "otorrinolaringología",
    "psiquiatra": "psiquiatría",
    "psicologo": "psicología",
    "psicólogo": "psicología",
    "nutricionista": "nutrición",
    "dentista": "odontología",
    "dental": "odontología",
    "rayos": "radiología",
    "análisis": "laboratorio",
    "sangre": "laboratorio",
    "fono": "fonoaudiología",
    "kinesio": "kinesiología",
    "fisioterapia": "kinesiología",
    "endocrino": "endocrinología",
}

# Relative date patterns
RELATIVE_DATES: dict[str, int] = {
    "hoy": 0,
    "mañana": 1,
    "pasado mañana": 2,
    "pasado": 2,
}

# Day of week patterns (Spanish)
DAYS_OF_WEEK: dict[str, int] = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

# Time patterns
TIME_PERIODS: dict[str, str] = {
    "mañana": "morning",
    "a la mañana": "morning",
    "por la mañana": "morning",
    "temprano": "morning",
    "mediodía": "noon",
    "mediodia": "noon",
    "tarde": "afternoon",
    "a la tarde": "afternoon",
    "por la tarde": "afternoon",
    "noche": "evening",
    "a la noche": "evening",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExtractedEntities:
    """Container for extracted entities.

    Attributes:
        specialty: Medical specialty mentioned.
        specialty_normalized: Normalized specialty name.
        date_text: Raw date text found.
        date_value: Parsed date value.
        time_text: Raw time text found.
        time_period: Time period (morning, afternoon, etc.).
        provider_name: Provider/doctor name mentioned.
        document: Patient document (DNI).
        phone: Phone number mentioned.
        selection: Numeric selection.
        raw_entities: Dictionary of all raw entities.
    """

    specialty: str | None = None
    specialty_normalized: str | None = None
    date_text: str | None = None
    date_value: date | None = None
    time_text: str | None = None
    time_period: str | None = None
    provider_name: str | None = None
    document: str | None = None
    phone: str | None = None
    selection: int | None = None
    raw_entities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {}

        if self.specialty:
            result["specialty"] = self.specialty
        if self.specialty_normalized:
            result["specialty_normalized"] = self.specialty_normalized
        if self.date_text:
            result["date_text"] = self.date_text
        if self.date_value:
            result["date_value"] = self.date_value.isoformat()
        if self.time_text:
            result["time_text"] = self.time_text
        if self.time_period:
            result["time_period"] = self.time_period
        if self.provider_name:
            result["provider_name"] = self.provider_name
        if self.document:
            result["document"] = self.document
        if self.phone:
            result["phone"] = self.phone
        if self.selection is not None:
            result["selection"] = self.selection

        return result

    @property
    def has_entities(self) -> bool:
        """Check if any entity was extracted."""
        return bool(
            self.specialty
            or self.date_text
            or self.time_text
            or self.provider_name
            or self.document
            or self.phone
            or self.selection is not None
        )


# =============================================================================
# Entity Extractor
# =============================================================================

class MedicalEntityExtractor:
    """Entity extractor for medical appointment conversations.

    Extracts specialties, dates, times, document numbers, and other
    relevant entities from user messages.

    Config options:
        specialty_list: Custom list of specialties to recognize.
        normalize_specialties: Whether to normalize specialty names.
    """

    def __init__(
        self,
        specialty_list: set[str] | None = None,
        normalize_specialties: bool = True,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize entity extractor.

        Args:
            specialty_list: Custom specialty list (uses default if None).
            normalize_specialties: Normalize specialty names to canonical form.
            config: Optional configuration dictionary.
        """
        self._specialties = specialty_list or MEDICAL_SPECIALTIES
        self._normalize = normalize_specialties
        self._config = config or {}

        logger.debug(
            f"MedicalEntityExtractor initialized with {len(self._specialties)} specialties"
        )

    async def extract(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> ExtractedEntities:
        """Extract entities from user message.

        Args:
            message: User message to analyze.
            context: Optional conversation context.

        Returns:
            ExtractedEntities with all found entities.
        """
        text_lower = message.lower().strip()
        entities = ExtractedEntities()

        # Extract each entity type
        entities.specialty = self._extract_specialty(text_lower)
        if entities.specialty and self._normalize:
            entities.specialty_normalized = self._normalize_specialty(entities.specialty)

        date_result = self._extract_date(text_lower)
        if date_result:
            entities.date_text, entities.date_value = date_result

        time_result = self._extract_time(text_lower)
        if time_result:
            entities.time_text, entities.time_period = time_result

        entities.provider_name = self._extract_provider_name(text_lower)
        entities.document = self._extract_document(text_lower)
        entities.phone = self._extract_phone(text_lower)
        entities.selection = self._extract_selection(text_lower, context)

        # Store raw entities
        entities.raw_entities = entities.to_dict()

        if entities.has_entities:
            logger.debug(f"Extracted entities: {entities.to_dict()}")

        return entities

    def _extract_specialty(self, text: str) -> str | None:
        """Extract medical specialty from text.

        Args:
            text: Lowercase message text.

        Returns:
            Specialty name or None.
        """
        # Check for exact specialty match
        for specialty in self._specialties:
            if specialty in text:
                return specialty

        # Check for specialty patterns (keywords that map to canonical names)
        for keyword in SPECIALTY_NORMALIZATION:
            if keyword in text:
                return keyword

        return None

    def _normalize_specialty(self, specialty: str) -> str:
        """Normalize specialty name to canonical form.

        Args:
            specialty: Raw specialty name.

        Returns:
            Normalized specialty name.
        """
        return SPECIALTY_NORMALIZATION.get(specialty.lower(), specialty)

    def _extract_date(self, text: str) -> tuple[str, date] | None:
        """Extract date from text.

        Args:
            text: Lowercase message text.

        Returns:
            Tuple of (raw_text, date) or None.
        """
        today = datetime.now().date()

        # Check relative dates
        for rel_date, days in RELATIVE_DATES.items():
            if rel_date in text:
                return (rel_date, today + timedelta(days=days))

        # Check day of week
        for day_name, day_num in DAYS_OF_WEEK.items():
            if day_name in text:
                # Find next occurrence of this weekday
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:  # Target day already passed this week
                    days_ahead += 7

                # Check for "próximo" / "proximo" (next week)
                if "próximo" in text or "proximo" in text:
                    if days_ahead <= 7:
                        days_ahead += 7

                return (day_name, today + timedelta(days=days_ahead))

        # Check for date patterns (DD/MM, DD-MM, etc.)
        date_pattern = r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?"
        match = re.search(date_pattern, text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year

            # Handle 2-digit year
            if year < 100:
                year += 2000

            try:
                parsed_date = date(year, month, day)
                return (match.group(0), parsed_date)
            except ValueError:
                pass

        return None

    def _extract_time(self, text: str) -> tuple[str, str] | None:
        """Extract time preference from text.

        Args:
            text: Lowercase message text.

        Returns:
            Tuple of (raw_text, time_period) or None.
        """
        # Check time periods
        for period_text, period_name in TIME_PERIODS.items():
            if period_text in text:
                return (period_text, period_name)

        # Check for specific time patterns (HH:MM, HH hs)
        time_pattern = r"(\d{1,2})(?::(\d{2}))?\s*(?:hs?|horas?)?"
        match = re.search(time_pattern, text)
        if match:
            hour = int(match.group(1))
            if 0 <= hour <= 23:
                period = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
                return (match.group(0), period)

        return None

    def _extract_provider_name(self, text: str) -> str | None:
        """Extract provider/doctor name from text.

        Args:
            text: Lowercase message text.

        Returns:
            Provider name or None.
        """
        # Patterns for doctor names
        patterns = [
            r"(?:doctor|doctora|dr\.?|dra\.?)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)?)",
            r"(?:con\s+el?\s*(?:doctor|doctora|dr\.?|dra\.?))\s+([a-záéíóúñ]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()

        return None

    def _extract_document(self, text: str) -> str | None:
        """Extract document number (DNI) from text.

        Args:
            text: Lowercase message text.

        Returns:
            Document number or None.
        """
        # DNI pattern: 7-8 digits, optionally with dots
        patterns = [
            r"\b(\d{2}\.?\d{3}\.?\d{3})\b",  # With dots (e.g., 12.345.678)
            r"\b(\d{7,8})\b",  # Without dots
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Remove dots for normalization
                doc = match.group(1).replace(".", "")
                if 7 <= len(doc) <= 8:
                    return doc

        return None

    def _extract_phone(self, text: str) -> str | None:
        """Extract phone number from text.

        Args:
            text: Lowercase message text.

        Returns:
            Phone number or None.
        """
        # Argentine phone patterns
        patterns = [
            r"\b((?:\+?54)?(?:9)?(?:11|2\d{2,3})\d{7,8})\b",  # Full format
            r"\b(\d{10,12})\b",  # Simple 10-12 digits
        ]

        for pattern in patterns:
            match = re.search(pattern, text.replace(" ", "").replace("-", ""))
            if match:
                return match.group(1)

        return None

    def _extract_selection(
        self,
        text: str,
        context: dict[str, Any] | None,
    ) -> int | None:
        """Extract numeric selection from text.

        Args:
            text: Lowercase message text.
            context: Conversation context.

        Returns:
            Selection number (0-based) or None.
        """
        # Only extract if we're expecting a selection
        if context and context.get("awaiting_selection"):
            if text.isdigit():
                selection = int(text)
                max_options = context.get("max_options", 10)
                if 1 <= selection <= max_options:
                    return selection - 1  # Convert to 0-based

        # Check for ordinal selections
        ordinals = {
            "primero": 0, "primera": 0, "1ro": 0, "1ra": 0,
            "segundo": 1, "segunda": 1, "2do": 1, "2da": 1,
            "tercero": 2, "tercera": 2, "3ro": 2, "3ra": 2,
            "cuarto": 3, "cuarta": 3, "4to": 3, "4ta": 3,
            "quinto": 4, "quinta": 4, "5to": 4, "5ta": 4,
        }

        for ordinal, index in ordinals.items():
            if ordinal in text:
                return index

        return None


# =============================================================================
# Factory Function
# =============================================================================

def get_medical_entity_extractor(
    specialty_list: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> MedicalEntityExtractor:
    """Factory function to create MedicalEntityExtractor.

    Args:
        specialty_list: Custom specialty list.
        config: Optional configuration.

    Returns:
        Configured MedicalEntityExtractor instance.
    """
    return MedicalEntityExtractor(
        specialty_list=specialty_list,
        config=config,
    )
