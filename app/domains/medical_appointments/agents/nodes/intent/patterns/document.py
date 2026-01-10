# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Document (DNI) intent pattern.
# ============================================================================
"""Document Pattern.

Detects DNI/document number input from user messages.
"""

import re
from typing import TYPE_CHECKING

from .base import IntentPattern, IntentResult

if TYPE_CHECKING:
    from ....state import MedicalAppointmentsState


class DocumentPattern(IntentPattern):
    """Pattern for detecting document (DNI) input.

    Matches 7-8 digit numbers (Argentine DNI format).
    """

    DNI_PATTERN = re.compile(r"\d{7,8}")

    @property
    def name(self) -> str:
        return "document"

    @property
    def priority(self) -> int:
        return 90  # High priority - check early

    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect DNI input."""
        cleaned = message.replace(".", "").replace(" ", "").strip()

        if re.match(r"^\d{7,8}$", cleaned):
            document = self._extract_document(cleaned)
            return IntentResult(
                detected=True,
                next_node="patient_identification",
                intent="patient_identification",
                state_updates={"patient_document": document},
            )
        return IntentResult()

    def _extract_document(self, message: str) -> str:
        """Extract document number from message."""
        match = self.DNI_PATTERN.search(message)
        return match.group() if match else ""
