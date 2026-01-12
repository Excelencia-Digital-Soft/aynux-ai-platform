"""
Pharmacy Info Handler

Handles queries about pharmacy information (address, phone, hours, email, website).
Uses LLM-driven ResponseGenerator for natural language responses.
"""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.utils.db_helpers import get_current_task
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
)
from app.tasks import TaskRegistry
from app.domains.pharmacy.services import (
    CapabilityQuestionDetector,
    PharmacyHoursFormatter,
    PharmacyInfoService,
)

from .base_handler import BasePharmacyHandler


class PharmacyInfoHandler(BasePharmacyHandler):
    """
    Handle pharmacy information queries.

    Responsibility: Orchestrate the flow of responding to pharmacy info queries.

    Answers questions like:
    - "¿Dónde queda la farmacia?"
    - "¿A qué hora abren?"
    - "¿Cuál es el teléfono?"
    - "¿Tienen página web?"
    """

    def __init__(
        self,
        response_generator: PharmacyResponseGenerator | None = None,
        capability_detector: CapabilityQuestionDetector | None = None,
        pharmacy_info_service: PharmacyInfoService | None = None,
        hours_formatter: PharmacyHoursFormatter | None = None,
    ):
        """
        Initialize the handler with injected dependencies.

        Args:
            response_generator: Optional ResponseGenerator instance
            capability_detector: Optional capability question detector
            pharmacy_info_service: Optional pharmacy info service
            hours_formatter: Optional hours formatter
        """
        super().__init__(response_generator)
        self._capability_detector = capability_detector or CapabilityQuestionDetector()
        self._pharmacy_info_service = pharmacy_info_service or PharmacyInfoService()
        self._hours_formatter = hours_formatter or PharmacyHoursFormatter()

    async def handle(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle pharmacy info query.

        Args:
            message: User question about pharmacy info
            state: Current state (must have pharmacy_id)

        Returns:
            State updates with pharmacy info response
        """
        state = state or {}
        customer_name = state.get("customer_name", "Cliente")
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"

        # PRIORITY: Check if this is a capability question
        if self._capability_detector.is_capability_question(message):
            self.logger.info(f"Capability question detected: '{message[:50]}...'")
            return await self._handle_capability_question(customer_name, pharmacy_name, state)

        # Handle pharmacy info queries (address, phone, hours, etc.)
        return await self._handle_info_query(message, state)

    async def _handle_capability_question(
        self,
        customer_name: str,
        pharmacy_name: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle questions about bot capabilities.

        Args:
            customer_name: Customer name for personalization
            pharmacy_name: Pharmacy name for context
            state: Current state

        Returns:
            State updates with capability response
        """
        response_state = {**state, "customer_name": customer_name, "pharmacy_name": pharmacy_name}
        result_content = await self._generate_response(
            intent="info_query_capability",
            state=response_state,
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_INFO_CAPABILITIES),
        )

        return self._format_state_update(
            message=result_content,
            intent_type="info_query",
            workflow_step="capability_query_answered",
            state=state,
        )

    async def _handle_info_query(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle pharmacy info queries (address, phone, hours, etc.).

        Args:
            message: User question
            state: Current state

        Returns:
            State updates with info response
        """
        customer_name = state.get("customer_name", "Cliente")
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"
        pharmacy_id_str = state.get("pharmacy_id")

        self.logger.info(f"Info query - pharmacy_id from state: {pharmacy_id_str}")

        # Load pharmacy config from database
        pharmacy_info = await self._pharmacy_info_service.get_pharmacy_info(pharmacy_id_str)
        self.logger.info(f"Info query - loaded pharmacy_info: {pharmacy_info}")

        if not pharmacy_info:
            return await self._handle_no_info(customer_name, pharmacy_name, state)

        # For general questions, use fallback directly (more reliable than LLM)
        if self._is_general_info_question(message):
            self.logger.info("General info question detected, using direct response")
            response = self._get_fallback_info_response(message, pharmacy_info)
        else:
            try:
                response = await self._generate_info_response_with_llm(
                    user_question=message,
                    customer_name=customer_name,
                    pharmacy_info=pharmacy_info,
                )
            except Exception as e:
                self.logger.warning(f"LLM info response failed, using fallback: {e}")
                response = self._get_fallback_info_response(message, pharmacy_info)

        return self._format_state_update(
            message=response,
            intent_type="info_query",
            workflow_step="info_query_answered",
            state=state,
        )

    async def _handle_no_info(
        self,
        customer_name: str,
        pharmacy_name: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle case when pharmacy info is not available.

        Args:
            customer_name: Customer name
            pharmacy_name: Pharmacy name
            state: Current state

        Returns:
            State updates with no-info response
        """
        response_state = {**state, "customer_name": customer_name, "pharmacy_name": pharmacy_name}
        result_content = await self._generate_response(
            intent="info_query_no_info",
            state=response_state,
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_INFO_NO_INFO),
        )

        return self._format_state_update(
            message=result_content,
            intent_type="info_query",
            workflow_step="info_query_no_data",
            state=state,
        )

    async def _generate_info_response_with_llm(
        self,
        user_question: str,
        customer_name: str,
        pharmacy_info: dict[str, Any],
    ) -> str:
        """
        Generate natural response using LLM.

        Args:
            user_question: User's question about pharmacy info
            customer_name: Customer name
            pharmacy_info: Pharmacy info dict

        Returns:
            Generated response or fallback
        """
        hours_text = self._hours_formatter.format(pharmacy_info)

        response_state = {
            "user_question": user_question,
            "customer_name": customer_name,
            "pharmacy_name": pharmacy_info.get("name", "la farmacia"),
            "pharmacy_address": pharmacy_info.get("address") or "No disponible",
            "pharmacy_phone": pharmacy_info.get("phone") or "No disponible",
            "pharmacy_email": pharmacy_info.get("email") or "No disponible",
            "pharmacy_website": pharmacy_info.get("website") or "No disponible",
            "pharmacy_hours": hours_text,
        }

        result_content = await self._generate_response(
            intent="info_query_generate",
            state=response_state,
            user_message=user_question,
            current_task=await get_current_task(TaskRegistry.PHARMACY_INFO_QUERY),
        )

        if result_content:
            return result_content
        return self._get_fallback_info_response(user_question, pharmacy_info)

    def _is_general_info_question(self, message: str) -> bool:
        """
        Check if the question is a general info request.

        General questions ask for all info, specific questions ask for
        one piece (address, phone, hours).

        Args:
            message: User message

        Returns:
            True if general info question
        """
        message_lower = message.lower()

        # General patterns - asking for all/general info
        general_patterns = [
            "info de la farmacia",
            "informacion de la farmacia",
            "información de la farmacia",
            "datos de la farmacia",
            "contacto de la farmacia",
            "info de contacto",
            "información de contacto",
            "datos de contacto",
            "como contactar",
            "cómo contactar",
        ]

        # Specific patterns - asking for one thing
        specific_patterns = [
            "direccion",
            "dirección",
            "donde queda",
            "dónde queda",
            "ubicacion",
            "ubicación",
            "horario",
            "hora",
            "abren",
            "cierran",
            "atienden",
            "telefono",
            "teléfono",
            "numero",
            "número",
            "llamar",
            "mail",
            "email",
            "correo",
            "web",
            "pagina",
            "página",
            "sitio",
        ]

        # Check if it's a general pattern
        for pattern in general_patterns:
            if pattern in message_lower:
                # But make sure it's not also specific
                has_specific = any(sp in message_lower for sp in specific_patterns)
                if not has_specific:
                    return True

        return False

    async def _get_fallback_capability_response(
        self,
        customer_name: str,
        pharmacy_name: str,
    ) -> str:
        """
        Fallback response when capability prompt fails to load.

        Args:
            customer_name: Customer name
            pharmacy_name: Pharmacy name

        Returns:
            Capability explanation
        """
        return await self._render_fallback_template(
            template_key="info_query_capability",
            variables={
                "customer_name": customer_name,
                "pharmacy_name": pharmacy_name,
            },
            yaml_file="pharmacy/fallback/fallback.yaml",
        )

    def _get_fallback_info_response(
        self,
        _: str,
        pharmacy_info: dict[str, Any],
    ) -> str:
        """
        Fallback response when LLM is unavailable.

        Args:
            question: User's question
            pharmacy_info: Pharmacy info dict

        Returns:
            Formatted info response
        """
        name = pharmacy_info.get("name", "La farmacia")
        address = pharmacy_info.get("address")
        phone = pharmacy_info.get("phone")
        email = pharmacy_info.get("email")
        website = pharmacy_info.get("website")
        hours_text = self._hours_formatter.format(pharmacy_info)

        parts = [f"**Información de {name}:**\n"]

        if address:
            parts.append(f"**Dirección:** {address}")
        if phone:
            parts.append(f"**Teléfono:** {phone}")
        if email:
            parts.append(f"**Email:** {email}")
        if website:
            parts.append(f"**Web:** {website}")
        if hours_text and hours_text != "No disponible":
            parts.append(f"\n**Horario:**\n{hours_text}")

        if len(parts) == 1:
            return "No tengo información de contacto de la farmacia disponible."

        return "\n".join(parts)
