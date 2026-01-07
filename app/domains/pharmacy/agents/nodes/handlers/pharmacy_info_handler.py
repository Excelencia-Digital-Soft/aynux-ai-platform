"""
Pharmacy Info Handler

Handles queries about pharmacy information (address, phone, hours, email, website).
Refactored to use SRP-compliant services and PromptRegistry.
"""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.services import (
    CapabilityQuestionDetector,
    PharmacyHoursFormatter,
    PharmacyInfoService,
)
from app.integrations.llm import ModelComplexity
from app.prompts.registry import PromptRegistry

from .base_handler import BasePharmacyHandler

# LLM configuration
INFO_QUERY_LLM_TEMPERATURE = 0.5


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
        prompt_manager=None,
        capability_detector: CapabilityQuestionDetector | None = None,
        pharmacy_info_service: PharmacyInfoService | None = None,
        hours_formatter: PharmacyHoursFormatter | None = None,
    ):
        """
        Initialize the handler with injected dependencies.

        Args:
            prompt_manager: Optional PromptManager instance
            capability_detector: Optional capability question detector
            pharmacy_info_service: Optional pharmacy info service
            hours_formatter: Optional hours formatter
        """
        super().__init__(prompt_manager)
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
        pharmacy_name = state.get("pharmacy_name", "la farmacia")

        # PRIORITY: Check if this is a capability question
        if self._capability_detector.is_capability_question(message):
            self.logger.info(f"Capability question detected: '{message[:50]}...'")
            return await self._handle_capability_question(
                customer_name, pharmacy_name, state
            )

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
        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_INFO_QUERY_CAPABILITY,
                variables={
                    "customer_name": customer_name,
                    "pharmacy_name": pharmacy_name,
                },
            )
        except Exception as e:
            self.logger.warning(f"Failed to load capability prompt: {e}")
            response = self._get_fallback_capability_response(customer_name, pharmacy_name)

        return self._format_state_update(
            message=response,
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
        pharmacy_name = state.get("pharmacy_name", "la farmacia")
        pharmacy_id_str = state.get("pharmacy_id")

        # Load pharmacy config from database
        pharmacy_info = await self._pharmacy_info_service.get_pharmacy_info(pharmacy_id_str)

        if not pharmacy_info:
            return await self._handle_no_info(customer_name, pharmacy_name, state)

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
        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_INFO_QUERY_NO_INFO,
                variables={
                    "customer_name": customer_name,
                    "pharmacy_name": pharmacy_name,
                },
            )
        except Exception as e:
            self.logger.warning(f"Failed to load no_info prompt: {e}")
            response = (
                f"Disculpa {customer_name}, no tengo acceso a la información "
                f"de contacto de {pharmacy_name} en este momento.\n\n"
                "Por favor, intenta comunicarte por otro medio."
            )

        return self._format_state_update(
            message=response,
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

        response = await self._generate_llm_response(
            template_key=PromptRegistry.PHARMACY_INFO_QUERY_GENERATE,
            variables={
                "user_question": user_question,
                "customer_name": customer_name,
                "pharmacy_name": pharmacy_info.get("name", "la farmacia"),
                "pharmacy_address": pharmacy_info.get("address") or "No disponible",
                "pharmacy_phone": pharmacy_info.get("phone") or "No disponible",
                "pharmacy_email": pharmacy_info.get("email") or "No disponible",
                "pharmacy_website": pharmacy_info.get("website") or "No disponible",
                "pharmacy_hours": hours_text,
                "is_24h": pharmacy_info.get("is_24h", False),
            },
            complexity=ModelComplexity.SIMPLE,
            temperature=INFO_QUERY_LLM_TEMPERATURE,
        )

        if response:
            return response
        return self._get_fallback_info_response(user_question, pharmacy_info)

    def _get_fallback_capability_response(
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
        return f"""¡Hola {customer_name}! Soy tu asistente virtual de {pharmacy_name}.

**Puedo ayudarte con:**
• **Consultar tu deuda** - Te muestro cuánto debes actualmente
• **Generar link de pago** - Para que pagues tu deuda de forma fácil
• **Pagos parciales** - Si quieres abonar una parte de tu deuda
• **Información de la farmacia** - Dirección, teléfono, horarios

Solo escríbeme lo que necesitas.

¿En qué puedo ayudarte hoy?"""

    def _get_fallback_info_response(
        self,
        question: str,
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
