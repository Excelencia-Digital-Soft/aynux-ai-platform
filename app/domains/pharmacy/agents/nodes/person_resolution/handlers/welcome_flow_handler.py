"""Handler for welcome message flow."""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.models import WelcomeFlowState
from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    REGISTRATION_STEP_NAME,
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.base_handler import (
    PersonResolutionBaseHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response


class WelcomeFlowHandler(PersonResolutionBaseHandler):
    """
    Handler for new user welcome flow.

    Responsibilities:
    - Show welcome message with 3 options
    - Handle option selection (existing/new/info)
    """

    async def show_welcome_message(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Show welcome message for new users with 3 options.

        CASO 1 from pharmacy_flujo_mejorado_v2.md:
        1️⃣ Sí, soy cliente → STEP_AWAITING_IDENTIFIER
        2️⃣ No, quiero registrarme → Registration flow
        3️⃣ Solo quiero información general → Info flow (no auth)

        If payment_amount is detected in state, acknowledge the payment intent
        and guide user to identify first.

        Args:
            state_dict: Current state

        Returns:
            State updates with welcome message
        """
        # Extract typed state for type safety
        flow_state = WelcomeFlowState.from_state(state_dict)
        pharmacy_name = flow_state.pharmacy_name or "la farmacia"

        response_state = {**state_dict, "pharmacy_name": pharmacy_name}

        # If user already expressed payment intent, acknowledge it
        # Task description comes from DB via response_config_cache
        if flow_state.has_payment_context():
            response_state["payment_amount"] = flow_state.payment_amount
            response_content = await generate_response(
                state=response_state,
                intent="welcome_with_payment_intent",
                user_message="",
            )
        else:
            response_content = await generate_response(
                state=response_state,
                intent="welcome_new_user",
                user_message="",
            )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_WELCOME,
            "identification_retries": 0,
            **self._preserve_all(state_dict),
        }

    async def handle_response(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user's response to welcome message (1/2/3).

        Args:
            message: User's response
            state_dict: Current state

        Returns:
            State updates routing to appropriate flow
        """
        message_clean = message.strip().lower()

        # Check for questions BEFORE confirmation patterns
        # Questions like "para qué verificar identidad?" should get an explanation
        # Uses DB-driven patterns via verification_question intent
        if await self._is_verification_question(message_clean, state_dict):
            return await self._explain_verification(state_dict, message)

        # Option 1: Existing client - ask for identifier (DB-driven patterns)
        if await self._match_confirmation_pattern(message_clean, "welcome_existing_client", state_dict):
            return await self._ask_for_identifier(state_dict)

        # Option 2: New client - route to registration (DB-driven patterns)
        if await self._match_confirmation_pattern(message_clean, "welcome_new_client", state_dict):
            return self._route_to_registration(state_dict)

        # Option 3: Just info - route to info flow (DB-driven patterns)
        if await self._match_confirmation_pattern(message_clean, "welcome_info_only", state_dict):
            return {
                "identification_step": None,
                "pharmacy_intent_type": "info_query",
                "next_node": "router",
                **self._preserve_all(state_dict),
            }

        # Option 4: User declines all options (DB-driven patterns)
        if await self._match_confirmation_pattern(message_clean, "welcome_decline", state_dict):
            return await self._handle_decline(state_dict, message)

        # Check if user sent a DNI directly (bypassing welcome options)
        # This handles cases like "quiero pagar" -> welcome -> "2259863" (DNI)
        if self._looks_like_dni(message):
            self.logger.info(f"Detected DNI input '{message}' during welcome flow, " "routing to identifier handler")
            return {
                "identification_step": STEP_AWAITING_IDENTIFIER,
                "pending_identifier_message": message,
                **self._preserve_all(state_dict),
            }

        # Ambiguous response - ask again
        # Task description comes from DB via response_config_cache
        response_content = await generate_response(
            state=state_dict,
            intent="ambiguous_welcome_response",
            user_message=message,
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_WELCOME,
            **self._preserve_all(state_dict),
        }

    def _looks_like_dni(self, message: str) -> bool:
        """
        Check if message looks like a DNI (Argentine document number).

        DNI format: 7-8 digits, optionally with dots (e.g., 22.598.630)
        Also accepts DNI with name (e.g., "22598630 Juan Perez")

        Args:
            message: User message to check

        Returns:
            True if message starts with or contains a DNI-like number
        """
        import re

        # Remove dots from message for easier matching
        cleaned = message.replace(".", "").strip()

        # Pattern: message starts with 6-11 digits (DNI range)
        # This catches: "22598630", "22598630 Juan Perez", etc.
        dni_pattern = r"^\d{6,11}(?:\s|$)"
        return bool(re.match(dni_pattern, cleaned))

    async def _ask_for_identifier(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask user for identifier (DNI/client number).

        Args:
            state_dict: Current state

        Returns:
            State updates asking for identifier
        """
        # Task description comes from DB via response_config_cache
        response_content = await generate_response(
            state=state_dict,
            intent="request_identifier",
            user_message="",
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "identification_retries": 0,
            **self._preserve_all(state_dict),
        }

    def _route_to_registration(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Route to customer registration flow.

        Args:
            state_dict: Current state

        Returns:
            State updates for registration
        """
        return {
            "identification_step": None,
            "awaiting_registration_data": True,
            "registration_step": REGISTRATION_STEP_NAME,
            "next_node": "customer_registration_node",
            **self._preserve_all(state_dict),
        }

    async def _is_verification_question(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> bool:
        """
        Detect if message is a question about identity verification.

        Uses DB-driven patterns via verification_question intent to check
        for question indicators and verification keywords.

        Args:
            message: Lowercase, stripped message
            state_dict: Current state for DB access

        Returns:
            True if message is a question about verification
        """
        if not message:
            return False

        # Use DB-driven pattern matching via verification_question intent
        # Patterns loaded from core.domain_intents table
        matched = await self._match_confirmation_pattern(message, "verification_question", state_dict)
        return matched

    async def _explain_verification(
        self,
        state_dict: dict[str, Any],
        user_message: str,
    ) -> dict[str, Any]:
        """
        Explain why identity verification is needed.

        Args:
            state_dict: Current state
            user_message: Original user message

        Returns:
            State updates with explanation, stays in welcome flow
        """
        # Task description comes from DB via response_config_cache
        response_content = await generate_response(
            state=state_dict,
            intent="explain_identity_verification",
            user_message=user_message,
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": STEP_AWAITING_WELCOME,
            **self._preserve_all(state_dict),
        }

    async def _handle_decline(
        self,
        state_dict: dict[str, Any],
        user_message: str,
    ) -> dict[str, Any]:
        """
        Handle when user declines all welcome options.

        Args:
            state_dict: Current state
            user_message: Original user message

        Returns:
            State updates offering alternative help
        """
        # Task description comes from DB via response_config_cache
        response_content = await generate_response(
            state=state_dict,
            intent="decline_welcome_options",
            user_message=user_message,
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "identification_step": None,
            "next_node": "router",
            **self._preserve_all(state_dict),
        }


__all__ = ["WelcomeFlowHandler"]
