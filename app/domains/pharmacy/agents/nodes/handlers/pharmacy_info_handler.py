"""
Pharmacy Info Handler

Handles queries about pharmacy information (address, phone, hours, email, website)
by fetching data from the pharmacy_merchant_configs table.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.integrations.llm import ModelComplexity

from .base_handler import BasePharmacyHandler

# LLM configuration
INFO_QUERY_LLM_TEMPERATURE = 0.5


class PharmacyInfoHandler(BasePharmacyHandler):
    """
    Handle pharmacy information queries.

    Answers questions like:
    - "¿Dónde queda la farmacia?"
    - "¿A qué hora abren?"
    - "¿Cuál es el teléfono?"
    - "¿Tienen página web?"
    """

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
        pharmacy_id_str = state.get("pharmacy_id")
        customer_name = state.get("customer_name", "Cliente")

        # Load pharmacy config from database
        pharmacy_info = await self._load_pharmacy_info(pharmacy_id_str)

        if not pharmacy_info:
            return self._format_state_update(
                message=self._get_no_info_response(customer_name),
                intent_type="info_query",
                workflow_step="info_query_no_data",
                state=state,
            )

        try:
            response = await self._generate_info_response_with_llm(
                user_question=message,
                customer_name=customer_name,
                pharmacy_info=pharmacy_info,
            )
        except Exception as e:
            self.logger.warning(f"LLM info response failed, using fallback: {e}")
            response = self._get_inline_info_response(message, pharmacy_info)

        return self._format_state_update(
            message=response,
            intent_type="info_query",
            workflow_step="info_query_answered",
            state=state,
        )

    async def _load_pharmacy_info(
        self,
        pharmacy_id_str: str | None,
    ) -> dict[str, Any] | None:
        """
        Load pharmacy information from database.

        Args:
            pharmacy_id_str: UUID string of the pharmacy config

        Returns:
            Dictionary with pharmacy info or None if not found
        """
        if not pharmacy_id_str:
            self.logger.warning("No pharmacy_id in state for info query")
            return None

        try:
            pharmacy_id = UUID(str(pharmacy_id_str))

            from app.core.tenancy.pharmacy_repository import PharmacyRepository
            from app.database.async_db import get_async_db_context

            async with get_async_db_context() as session:
                repo = PharmacyRepository(session)
                config = await repo.get_by_id(pharmacy_id)

            if not config:
                self.logger.warning(f"Pharmacy config not found: {pharmacy_id}")
                return None

            return {
                "name": config.pharmacy_name,
                "address": config.pharmacy_address,
                "phone": config.pharmacy_phone,
                "email": config.pharmacy_email,
                "website": config.pharmacy_website,
                "hours": config.pharmacy_hours,
                "is_24h": config.pharmacy_is_24h,
            }
        except ValueError as e:
            self.logger.error(f"Invalid pharmacy_id format: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading pharmacy info: {e}", exc_info=True)
            return None

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
        hours_text = self._format_hours(pharmacy_info)

        response = await self._generate_llm_response(
            template_key="pharmacy.info_query.generate",
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
        return self._get_inline_info_response(user_question, pharmacy_info)

    def _format_hours(self, pharmacy_info: dict[str, Any]) -> str:
        """
        Format operating hours for display.

        Args:
            pharmacy_info: Pharmacy info dict

        Returns:
            Formatted hours string
        """
        if pharmacy_info.get("is_24h"):
            return "Abierto 24 horas, todos los días"

        hours = pharmacy_info.get("hours")
        if not hours or not isinstance(hours, dict):
            return "No disponible"

        lines = []
        for day, time_range in hours.items():
            lines.append(f"  - {day}: {time_range}")
        return "\n".join(lines) if lines else "No disponible"

    def _get_inline_info_response(
        self,
        question: str,
        pharmacy_info: dict[str, Any],
    ) -> str:
        """
        Fallback response when LLM unavailable.

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
        hours_text = self._format_hours(pharmacy_info)

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

    def _get_no_info_response(self, customer_name: str) -> str:
        """
        Response when pharmacy info is unavailable.

        Args:
            customer_name: Customer name

        Returns:
            Apology message
        """
        return (
            f"Disculpa {customer_name}, no tengo acceso a la información "
            "de contacto de la farmacia en este momento.\n\n"
            "Por favor, intenta comunicarte por otro medio."
        )
