"""
SmartInputInterpreter facade.

Composes all interpreters and maintains backward-compatible API.
"""

from typing import TYPE_CHECKING

from app.integrations.llm import OllamaLLM

from .base import InterpretationResult
from .confirmation_interpreter import ConfirmationInterpreter
from .description_checker import DescriptionQualityChecker
from .incident_detector import IncidentIntentDetector
from .priority_interpreter import PriorityInterpreter

if TYPE_CHECKING:
    from app.domains.excelencia.application.services.query_type_detector import (
        CompositeQueryTypeDetector,
    )


class SmartInputInterpreter:
    """
    Facade that composes all input interpreters.

    Maintains backward-compatible API while delegating to specialized classes.
    """

    def __init__(self) -> None:
        """Initialize all interpreters."""
        self._priority = PriorityInterpreter()
        self._confirmation = ConfirmationInterpreter()
        self._description = DescriptionQualityChecker()
        self._incident = IncidentIntentDetector()

    async def interpret_priority(
        self,
        message: str,
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """Interpret priority selection."""
        return await self._priority.interpret(message, llm)

    async def interpret_confirmation(
        self,
        message: str,
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """Interpret user confirmation."""
        return await self._confirmation.interpret(message, llm)

    async def check_description_quality(
        self,
        description: str,
        llm: OllamaLLM,
    ) -> tuple[bool, str | None]:
        """Check description quality."""
        return await self._description.check(description, llm)

    async def detect_incident_intent(
        self,
        message: str,
        query_type_detector: "CompositeQueryTypeDetector",
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """Detect incident creation intent."""
        return await self._incident.detect(message, query_type_detector, llm)

    def get_priority_display(self, priority_value: str) -> str:
        """Get display name for a priority value."""
        return self._priority.get_display_name(priority_value)
