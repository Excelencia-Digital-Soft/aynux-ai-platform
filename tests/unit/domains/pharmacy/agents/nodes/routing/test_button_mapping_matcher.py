"""Tests for ButtonMappingMatcher and KnownListItemMatcher."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext
from app.domains.pharmacy.agents.nodes.routing.matchers.button_mapping import (
    ButtonMappingMatcher,
    KnownListItemMatcher,
)


@dataclass
class MockRoutingConfigDTO:
    """Mock RoutingConfigDTO for testing."""

    id: str
    config_type: str
    trigger_value: str
    target_intent: str
    target_node: str | None
    priority: int
    requires_auth: bool
    clears_context: bool
    metadata: dict[str, Any] | None
    display_name: str | None


@pytest.fixture
def button_matcher() -> ButtonMappingMatcher:
    """Create a ButtonMappingMatcher instance."""
    return ButtonMappingMatcher()


@pytest.fixture
def list_item_matcher() -> KnownListItemMatcher:
    """Create a KnownListItemMatcher instance."""
    return KnownListItemMatcher()


@pytest.fixture
def mock_config_loader() -> MagicMock:
    """Create a mock config loader."""
    loader = MagicMock()
    loader.escape_intents = frozenset()
    return loader


def create_config(
    trigger: str,
    intent: str,
    node: str | None = None,
    text_aliases: list[str] | None = None,
    text_alias: str | None = None,
) -> MockRoutingConfigDTO:
    """Helper to create mock config."""
    metadata = {}
    if text_aliases:
        metadata["text_aliases"] = text_aliases
    if text_alias:
        metadata["text_alias"] = text_alias
    return MockRoutingConfigDTO(
        id="test-id",
        config_type="button_mapping",
        trigger_value=trigger,
        target_intent=intent,
        target_node=node,
        priority=50,
        requires_auth=False,
        clears_context=False,
        metadata=metadata if metadata else None,
        display_name=None,
    )


def create_context(
    message: str,
    config_loader: MagicMock,
    awaiting: str | None = None,
) -> MatchContext:
    """Helper to create match context."""
    return MatchContext(
        message=message,
        message_lower=message.strip().lower(),
        state={},
        config_loader=config_loader,
        awaiting=awaiting,
        current_intent=None,
    )


class TestButtonMappingMatcherPriority:
    """Tests for matcher priority."""

    def test_priority_is_50(self, button_matcher):
        """Test that priority is 50."""
        assert button_matcher.priority == 50


class TestButtonMappingMatcherMatches:
    """Tests for ButtonMappingMatcher matches method."""

    @pytest.mark.asyncio
    async def test_matches_exact_button_id(self, button_matcher, mock_config_loader):
        """Test matching exact button ID."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("btn_pay_full", "pay_full", "payment_processor"),
        ]
        ctx = create_context("btn_pay_full", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None
        assert result.match_type == "button_mapping"
        assert result.handler_key == "button_selection"
        assert result.config.target_intent == "pay_full"

    @pytest.mark.asyncio
    async def test_matches_case_sensitive_button_id(self, button_matcher, mock_config_loader):
        """Test that button ID matching is case-sensitive for exact match."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("btn_Pay_Full", "pay_full"),
        ]
        ctx = create_context("btn_Pay_Full", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_no_match_for_different_case(self, button_matcher, mock_config_loader):
        """Test no match when case doesn't match for button ID."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("btn_pay_full", "pay_full"),
        ]
        ctx = create_context("BTN_PAY_FULL", mock_config_loader)

        result = await button_matcher.matches(ctx)

        # Button IDs should match the stored value exactly
        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_when_no_configs(self, button_matcher, mock_config_loader):
        """Test no match when no button_mapping configs exist."""
        mock_config_loader.get_configs_by_type.return_value = []
        ctx = create_context("btn_pay_full", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_matches_text_alias(self, button_matcher, mock_config_loader):
        """Test matching via text_alias metadata."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config(
                "btn_add_new_person",
                "add_new_person",
                text_alias="agregar persona",
            ),
        ]
        ctx = create_context("agregar persona", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None
        assert result.config.trigger_value == "btn_add_new_person"

    @pytest.mark.asyncio
    async def test_matches_text_aliases_list(self, button_matcher, mock_config_loader):
        """Test matching via text_aliases list in metadata."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config(
                "btn_confirm",
                "confirm_yes",
                text_aliases=["si", "confirmar", "ok"],
            ),
        ]
        ctx = create_context("confirmar", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "confirm_yes"

    @pytest.mark.asyncio
    async def test_text_alias_case_insensitive(self, button_matcher, mock_config_loader):
        """Test that text alias matching is case-insensitive."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config(
                "btn_add",
                "add_person",
                text_alias="Agregar Persona",
            ),
        ]
        ctx = create_context("AGREGAR PERSONA", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None


class TestButtonMappingMatcherEdgeCases:
    """Edge case tests for ButtonMappingMatcher."""

    @pytest.mark.asyncio
    async def test_empty_message(self, button_matcher, mock_config_loader):
        """Test with empty message."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("btn_pay", "pay"),
        ]
        ctx = create_context("", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_metadata(self, button_matcher, mock_config_loader):
        """Test config without metadata."""
        config = create_config("btn_pay", "pay")
        config.metadata = None
        mock_config_loader.get_configs_by_type.return_value = [config]
        ctx = create_context("btn_pay", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_strips_whitespace(self, button_matcher, mock_config_loader):
        """Test that message whitespace is stripped."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("btn_pay", "pay"),
        ]
        ctx = create_context("  btn_pay  ", mock_config_loader)

        result = await button_matcher.matches(ctx)

        assert result is not None


class TestKnownListItemMatcherPriority:
    """Tests for KnownListItemMatcher priority."""

    def test_priority_is_45(self, list_item_matcher):
        """Test that priority is 45."""
        assert list_item_matcher.priority == 45


class TestKnownListItemMatcherMatches:
    """Tests for KnownListItemMatcher matches method."""

    @pytest.mark.asyncio
    async def test_matches_agregar_persona(self, list_item_matcher, mock_config_loader):
        """Test matching 'agregar persona' pattern."""
        ctx = create_context("agregar persona", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result is not None
        assert result.match_type == "known_list_item"
        assert result.handler_key == "known_list_item"
        assert result.metadata["intent"] == "add_new_person"
        assert result.metadata["next_node"] == "auth_plex"

    @pytest.mark.asyncio
    async def test_matches_btn_add_new_person(self, list_item_matcher, mock_config_loader):
        """Test matching 'btn_add_new_person' pattern."""
        ctx = create_context("btn_add_new_person", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result is not None
        assert result.metadata["intent"] == "add_new_person"

    @pytest.mark.asyncio
    async def test_strips_trailing_dots(self, list_item_matcher, mock_config_loader):
        """Test that trailing dots are stripped (WhatsApp may add '...')."""
        ctx = create_context("agregar persona...", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result is not None
        assert result.metadata["intent"] == "add_new_person"

    @pytest.mark.asyncio
    async def test_no_match_for_unknown_pattern(self, list_item_matcher, mock_config_loader):
        """Test no match for unknown patterns."""
        ctx = create_context("quiero pagar", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_case_insensitive(self, list_item_matcher, mock_config_loader):
        """Test that matching is case-insensitive."""
        ctx = create_context("AGREGAR PERSONA", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_metadata_contains_awaiting_input(self, list_item_matcher, mock_config_loader):
        """Test that result metadata contains awaiting_input."""
        ctx = create_context("agregar persona", mock_config_loader)

        result = await list_item_matcher.matches(ctx)

        assert result.metadata["awaiting_input"] == "account_number"
