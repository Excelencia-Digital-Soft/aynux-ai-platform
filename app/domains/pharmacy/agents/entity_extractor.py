"""
Pharmacy Entity Extractor

Extract amounts, DNI, dates and other entities from pharmacy messages.
"""

from __future__ import annotations

import re
from typing import Any


class PharmacyEntityExtractor:
    """Extract pharmacy-relevant entities from messages."""

    # Amount patterns
    MIL_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*mil(?:es)?\b")
    MILLON_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*millon(?:es)?\b")
    FORMATTED_AMOUNT_PATTERN = re.compile(r"\$?\s*(\d{1,3}(?:[.,]\d{3})+)")
    PLAIN_AMOUNT_PATTERN = re.compile(r"\$?\s*(\d{4,})")
    SIMPLE_AMOUNT_PATTERN = re.compile(r"\$?\s*(\d+)")

    # DNI pattern (7-8 digits)
    DNI_PATTERN = re.compile(r"\b(\d{7,8})\b")

    def extract(self, doc: Any, text_lower: str) -> dict[str, Any]:
        """
        Extract pharmacy-relevant entities from message.

        Args:
            doc: spaCy Doc object (can be None)
            text_lower: Lowercase message text

        Returns:
            Dictionary with extracted entities
        """
        entities: dict[str, Any] = {
            "amount": None,
            "date": None,
            "document_number": None,
        }

        # Extract amount
        entities["amount"] = self._extract_amount(text_lower)

        # Extract DNI
        entities["document_number"] = self._extract_dni(text_lower)

        # Extract from spaCy NER if available
        if doc is not None:
            self._extract_from_spacy(doc, entities)

        return entities

    def _extract_amount(self, text_lower: str) -> float | None:
        """
        Extract monetary amount from text.

        Handles Spanish patterns: "50 mil", "2 millones", "$50.000", "50000"
        """
        # Try "mil" pattern first (e.g., "50 mil" = 50000)
        if mil_matches := self.MIL_PATTERN.findall(text_lower):
            try:
                base_num = float(mil_matches[0].replace(".", "").replace(",", "."))
                return base_num * 1000
            except ValueError:
                pass

        # Try "millones" pattern (e.g., "2 millones" = 2000000)
        if millon_matches := self.MILLON_PATTERN.findall(text_lower):
            try:
                base_num = float(millon_matches[0].replace(".", "").replace(",", "."))
                return base_num * 1000000
            except ValueError:
                pass

        # Try formatted pattern with thousand separators (e.g., "50.000" or "1.234.567")
        if formatted_matches := self.FORMATTED_AMOUNT_PATTERN.findall(text_lower):
            return self._parse_amount_string(formatted_matches[0])

        # Try plain pattern (4+ digits without separators, e.g., "50000")
        if plain_matches := self.PLAIN_AMOUNT_PATTERN.findall(text_lower):
            return self._parse_amount_string(plain_matches[0])

        # Try simple pattern (any number)
        if simple_matches := self.SIMPLE_AMOUNT_PATTERN.findall(text_lower):
            return self._parse_amount_string(simple_matches[0])

        return None

    def _parse_amount_string(self, amount_str: str) -> float | None:
        """Parse amount string removing thousand separators."""
        try:
            # Remove thousand separators (. or ,) and convert decimal separator
            cleaned = amount_str.replace(".", "").replace(",", ".")
            return float(cleaned)
        except ValueError:
            return None

    def _extract_dni(self, text_lower: str) -> str | None:
        """Extract DNI (7-8 digit document number)."""
        if dni_matches := self.DNI_PATTERN.findall(text_lower):
            return dni_matches[0]
        return None

    def _extract_from_spacy(self, doc: Any, entities: dict[str, Any]) -> None:
        """Extract entities using spaCy NER."""
        for ent in doc.ents:
            if ent.label_ == "MONEY" and entities["amount"] is None:
                try:
                    entities["amount"] = float(re.sub(r"[^\d.]", "", ent.text))
                except ValueError:
                    pass
            elif ent.label_ in ("DATE", "TIME"):
                entities["date"] = ent.text
