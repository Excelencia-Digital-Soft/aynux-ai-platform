"""Tests for auth_plex_node - Account Number and DNI authentication flows."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.domains.pharmacy.agents.nodes.auth_plex_node import (
    AuthPlexService,
    _handle_account_not_found_selection,
    _handle_account_number_input,
    auth_plex_node,
)


class TestAuthPlexService:
    """Test suite for AuthPlexService."""

    class TestSearchByCustomerId:
        """Tests for search_by_customer_id method."""

        @pytest.mark.asyncio
        async def test_returns_customer_when_found(self):
            """Test returning customer dict when found by customer_id."""
            service = AuthPlexService()

            # Mock the plex client
            mock_customer = AsyncMock()
            mock_customer.id = 9176
            mock_customer.nombre = "Juan Perez"
            mock_customer.documento = "12345678"
            mock_customer.telefono = "123456789"
            mock_customer.is_valid_for_identification = True

            mock_plex_client = AsyncMock()
            mock_plex_client.search_customer = AsyncMock(return_value=[mock_customer])
            mock_plex_client.__aenter__ = AsyncMock(return_value=mock_plex_client)
            mock_plex_client.__aexit__ = AsyncMock(return_value=None)

            with patch.object(service, "_get_plex_client", return_value=mock_plex_client):
                result = await service.search_by_customer_id(9176)

            assert result is not None
            assert result["id"] == 9176
            assert result["nombre"] == "Juan Perez"

        @pytest.mark.asyncio
        async def test_returns_none_when_not_found(self):
            """Test returning None when customer_id not found."""
            service = AuthPlexService()

            mock_plex_client = AsyncMock()
            mock_plex_client.search_customer = AsyncMock(return_value=[])
            mock_plex_client.__aenter__ = AsyncMock(return_value=mock_plex_client)
            mock_plex_client.__aexit__ = AsyncMock(return_value=None)

            with patch.object(service, "_get_plex_client", return_value=mock_plex_client):
                result = await service.search_by_customer_id(9999)

            assert result is None


class TestHandleAccountNumberInput:
    """Tests for _handle_account_number_input function."""

    @pytest.mark.asyncio
    async def test_valid_account_authenticates_user(self):
        """Test that valid account number authenticates the user."""
        service = AuthPlexService()
        state = {"messages": [], "error_count": 0}

        mock_customer = {
            "id": 9176,
            "nombre": "Juan Perez",
            "documento": "12345678",
            "telefono": "123456789",
        }

        with patch.object(service, "search_by_customer_id", return_value=mock_customer):
            result = await _handle_account_number_input(service, "9176", state)

        assert result["is_authenticated"] is True
        assert result["plex_user_id"] == 9176
        assert result["customer_name"] == "Juan Perez"
        assert result["next_node"] == "main_menu_node"

    @pytest.mark.asyncio
    async def test_invalid_account_shows_options(self):
        """Test that invalid account number shows retry/DNI options."""
        service = AuthPlexService()
        state = {"messages": [], "error_count": 0}

        with patch.object(service, "search_by_customer_id", return_value=None):
            result = await _handle_account_number_input(service, "9999", state)

        assert result.get("is_authenticated") is not True
        assert result["awaiting_input"] == "account_not_found"
        assert result["pending_account_number"] == "9999"
        assert result["next_node"] == "response_formatter"

    @pytest.mark.asyncio
    async def test_empty_input_stays_on_account_number(self):
        """Test that empty input stays on account_number awaiting."""
        service = AuthPlexService()
        state = {"messages": [], "error_count": 0}

        result = await _handle_account_number_input(service, "", state)

        assert result["awaiting_input"] == "account_number"
        assert result["error_count"] == 1

    @pytest.mark.asyncio
    async def test_extracts_digits_only(self):
        """Test that non-digit characters are stripped."""
        service = AuthPlexService()
        state = {"messages": [], "error_count": 0}

        mock_customer = {"id": 9176, "nombre": "Juan", "documento": "12345678", "telefono": "123"}

        with patch.object(service, "search_by_customer_id", return_value=mock_customer) as mock_search:
            await _handle_account_number_input(service, "Mi cuenta es 9176", state)

        # Should have called with just the digits
        mock_search.assert_called_once_with(9176)


class TestHandleAccountNotFoundSelection:
    """Tests for _handle_account_not_found_selection function."""

    @pytest.mark.asyncio
    async def test_retry_button_goes_to_account_number(self):
        """Test that retry button returns to account_number flow."""
        result = await _handle_account_not_found_selection("btn_retry_account")

        assert result["awaiting_input"] == "account_number"
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_validate_dni_button_goes_to_dni(self):
        """Test that validate DNI button switches to DNI flow."""
        result = await _handle_account_not_found_selection("btn_validate_dni")

        assert result["awaiting_input"] == "dni"
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_text_with_intentar_goes_to_account_number(self):
        """Test that text containing 'intentar' goes to account_number."""
        result = await _handle_account_not_found_selection("quiero intentar de nuevo")

        assert result["awaiting_input"] == "account_number"

    @pytest.mark.asyncio
    async def test_text_with_dni_goes_to_dni(self):
        """Test that text containing 'dni' goes to DNI flow."""
        result = await _handle_account_not_found_selection("prefiero validar con dni")

        assert result["awaiting_input"] == "dni"

    @pytest.mark.asyncio
    async def test_unrecognized_stays_on_account_not_found(self):
        """Test that unrecognized input stays on account_not_found."""
        result = await _handle_account_not_found_selection("no se que hacer")

        assert result["awaiting_input"] == "account_not_found"


class TestAuthPlexNodeFlow:
    """Integration tests for auth_plex_node main flow."""

    @pytest.mark.asyncio
    async def test_unauthenticated_user_gets_account_number_request(self):
        """Test that unauthenticated user without phone match gets account_number request."""
        state = {
            "messages": [HumanMessage(content="hola")],
            "is_authenticated": False,
            "user_phone": "5491234567890",
            "awaiting_input": None,
        }

        with patch.object(AuthPlexService, "search_by_phone", return_value=None):
            result = await auth_plex_node(state)

        assert result["awaiting_input"] == "account_number"
        assert result["next_node"] == "response_formatter"

    @pytest.mark.asyncio
    async def test_phone_match_authenticates_directly(self):
        """Test that phone match authenticates user directly."""
        state = {
            "messages": [HumanMessage(content="hola")],
            "is_authenticated": False,
            "user_phone": "5491234567890",
            "awaiting_input": None,
        }

        mock_customer = {"id": 9176, "nombre": "Juan", "documento": "12345678", "telefono": "5491234567890"}

        with patch.object(AuthPlexService, "search_by_phone", return_value=mock_customer):
            result = await auth_plex_node(state)

        assert result["is_authenticated"] is True
        assert result["plex_user_id"] == 9176
        assert result["next_node"] == "main_menu_node"

    @pytest.mark.asyncio
    async def test_awaiting_account_number_processes_input(self):
        """Test that awaiting_input=account_number processes the account number."""
        state = {
            "messages": [HumanMessage(content="9176")],
            "is_authenticated": False,
            "awaiting_input": "account_number",
            "error_count": 0,
        }

        mock_customer = {"id": 9176, "nombre": "Juan", "documento": "12345678", "telefono": "123"}

        with patch.object(AuthPlexService, "search_by_customer_id", return_value=mock_customer):
            result = await auth_plex_node(state)

        assert result["is_authenticated"] is True
        assert result["plex_user_id"] == 9176

    @pytest.mark.asyncio
    async def test_awaiting_account_not_found_processes_selection(self):
        """Test that awaiting_input=account_not_found processes button selection."""
        state = {
            "messages": [HumanMessage(content="btn_validate_dni")],
            "is_authenticated": False,
            "awaiting_input": "account_not_found",
        }

        result = await auth_plex_node(state)

        assert result["awaiting_input"] == "dni"
