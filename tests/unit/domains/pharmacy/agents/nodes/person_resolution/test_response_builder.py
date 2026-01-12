"""
Unit tests for ResponseBuilder service.
"""

from __future__ import annotations

import pytest

from app.domains.pharmacy.agents.nodes.person_resolution.services.response_builder import (
    ResponseBuilder,
)


class TestResponseBuilder:
    """Test suite for ResponseBuilder."""

    def test_init(self):
        """Test service initialization."""
        builder = ResponseBuilder()
        assert builder is not None

    @pytest.mark.asyncio
    async def test_build_success_state_basic(self):
        """Test building basic success state."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
            "pharmacy_phone": "+54911000000",
        }
        updates = {"customer_identified": True}

        result = await builder.build_success_state(state_dict, updates)

        assert result["customer_identified"] is True
        assert result["pharmacy_name"] == "Farmacia Test"
        assert result["pharmacy_phone"] == "+54911000000"

    @pytest.mark.asyncio
    async def test_build_success_state_with_payment(self):
        """Test building success state with payment context."""
        builder = ResponseBuilder()
        state_dict = {
            "payment_amount": 3000.0,
            "pharmacy_name": "Farmacia Test",
        }
        updates = {"customer_identified": True}

        result = await builder.build_success_state(state_dict, updates)

        assert result["customer_identified"] is True
        assert result["payment_amount"] == 3000.0

    @pytest.mark.asyncio
    async def test_build_info_query_state(self):
        """Test building info query state."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
            "payment_amount": 5000.0,
        }

        result = await builder.build_info_query_state(state_dict)

        assert result["pharmacy_intent_type"] == "info_query"
        assert result["next_node"] == "router"
        assert result["pharmacy_name"] == "Farmacia Test"
        assert result["payment_amount"] == 5000.0

    @pytest.mark.asyncio
    async def test_build_welcome_request_state(self):
        """Test building welcome request state."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
            "payment_amount": 2000.0,
        }

        result = await builder.build_welcome_request_state(state_dict)

        assert result["pharmacy_name"] == "Farmacia Test"
        assert result["payment_amount"] == 2000.0

    @pytest.mark.asyncio
    async def test_build_identifier_request_state(self):
        """Test building identifier request state."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
        }

        result = await builder.build_identifier_request_state(state_dict)

        assert "messages" in result
        assert result["identification_retries"] == 0
        assert result["pharmacy_name"] == "Farmacia Test"

    @pytest.mark.asyncio
    async def test_build_identifier_request_state_with_pending_flow(self):
        """Test building identifier request state with pending flow."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
        }

        result = await builder.build_identifier_request_state(state_dict, pending_flow="payment")

        assert result["pending_flow"] == "payment"
        assert result["identification_retries"] == 0

    @pytest.mark.asyncio
    async def test_build_proceed_with_customer_state_self(self):
        """Test building proceed state for self customer."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
            "payment_amount": 3000.0,
        }
        plex_customer = {
            "id": "12345",
            "nombre": "Juan Pérez",
        }

        result = await builder.build_proceed_with_customer_state(
            plex_customer, state_dict, is_self=True
        )

        assert result["plex_customer_id"] == "12345"
        assert result["customer_name"] == "Juan Pérez"
        assert result["customer_identified"] is True
        assert result["is_self"] is True
        assert result["awaiting_own_or_other"] is False
        assert result["next_node"] == "debt_check_node"
        assert result["pharmacy_name"] == "Farmacia Test"
        assert result["payment_amount"] == 3000.0

    @pytest.mark.asyncio
    async def test_build_proceed_with_customer_state_other(self):
        """Test building proceed state for other customer."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
        }
        plex_customer = {
            "id": "12345",
            "nombre": "María García",
        }

        result = await builder.build_proceed_with_customer_state(
            plex_customer, state_dict, is_self=False
        )

        assert result["plex_customer_id"] == "12345"
        assert result["customer_name"] == "María García"
        assert result["is_self"] is False

    @pytest.mark.asyncio
    async def test_build_validation_request_state_self(self):
        """Test building validation request state for self."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
            "payment_amount": 4000.0,
        }

        result = await builder.build_validation_request_state(state_dict, is_for_other=False)

        assert result["validation_step"] == "dni"
        assert result["is_querying_for_other"] is False
        assert result["next_node"] == "person_validation_node"
        assert result["pharmacy_name"] == "Farmacia Test"
        assert result["payment_amount"] == 4000.0

    @pytest.mark.asyncio
    async def test_build_validation_request_state_other(self):
        """Test building validation request state for other."""
        builder = ResponseBuilder()
        state_dict = {
            "pharmacy_name": "Farmacia Test",
        }

        result = await builder.build_validation_request_state(state_dict, is_for_other=True)

        assert result["validation_step"] == "dni"
        assert result["is_querying_for_other"] is True
        assert result["next_node"] == "person_validation_node"

    @pytest.mark.asyncio
    async def test_state_preservation_across_methods(self):
        """Test that state is preserved across different builder methods."""
        builder = ResponseBuilder()
        state_dict = {
            "payment_amount": 3000.0,
            "pharmacy_name": "Farmacia Test",
            "pharmacy_phone": "+54911000000",
            "pharmacy_intent_type": "debt_query",
        }

        # Build different states
        info_state = await builder.build_info_query_state(state_dict)
        welcome_state = await builder.build_welcome_request_state(state_dict)

        # Verify context is preserved
        assert info_state["payment_amount"] == 3000.0
        assert info_state["pharmacy_name"] == "Farmacia Test"
        assert welcome_state["payment_amount"] == 3000.0
        assert welcome_state["pharmacy_name"] == "Farmacia Test"

    @pytest.mark.asyncio
    async def test_build_success_state_no_preserved_fields(self):
        """Test building success state with no preserved fields."""
        builder = ResponseBuilder()
        state_dict = {}
        updates = {"customer_identified": True}

        result = await builder.build_success_state(state_dict, updates)

        assert result["customer_identified"] is True

    def test_build_with_db_session(self):
        """Test builder with db session."""
        # This test verifies that db_session parameter is accepted
        # Actual DB operations are tested elsewhere
        builder = ResponseBuilder(db_session=None)
        assert builder is not None


__all__ = ["TestResponseBuilder"]
