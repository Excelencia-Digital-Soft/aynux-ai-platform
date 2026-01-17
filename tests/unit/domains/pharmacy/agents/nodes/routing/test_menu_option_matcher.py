"""Tests for MenuOptionMatcher - Menu option matching for routing."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext
from app.domains.pharmacy.agents.nodes.routing.matchers.menu_option import (
    EMOJI_MAP,
    MenuOptionMatcher,
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
def matcher() -> MenuOptionMatcher:
    """Create a MenuOptionMatcher instance."""
    return MenuOptionMatcher()


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
) -> MockRoutingConfigDTO:
    """Helper to create mock config."""
    return MockRoutingConfigDTO(
        id="test-id",
        config_type="menu_option",
        trigger_value=trigger,
        target_intent=intent,
        target_node=node,
        priority=40,
        requires_auth=False,
        clears_context=False,
        metadata=None,
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


class TestMenuOptionMatcherPriority:
    """Tests for matcher priority."""

    def test_priority_is_40(self, matcher):
        """Test that priority is 40."""
        assert matcher.priority == 40


class TestMenuOptionMatcherMenuContext:
    """Tests for menu context requirement."""

    @pytest.mark.asyncio
    async def test_no_match_when_not_in_menu_context(self, matcher, mock_config_loader):
        """Test no match when not awaiting menu_selection."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "debt_query", "debt_manager"),
        ]
        ctx = create_context("1", mock_config_loader, awaiting=None)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_when_awaiting_other_input(self, matcher, mock_config_loader):
        """Test no match when awaiting different input type."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "debt_query"),
        ]
        ctx = create_context("1", mock_config_loader, awaiting="dni")

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_matches_when_in_menu_context(self, matcher, mock_config_loader):
        """Test match when awaiting menu_selection."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "debt_query", "debt_manager"),
        ]
        ctx = create_context("1", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.match_type == "menu_option"
        assert result.handler_key == "menu_option"


class TestMenuOptionMatcherNumericOptions:
    """Tests for numeric menu option matching."""

    @pytest.mark.asyncio
    async def test_matches_option_1(self, matcher, mock_config_loader):
        """Test matching menu option 1."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "debt_query", "debt_manager"),
        ]
        ctx = create_context("1", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "debt_query"

    @pytest.mark.asyncio
    async def test_matches_option_0(self, matcher, mock_config_loader):
        """Test matching menu option 0 (exit)."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("0", "farewell", "farewell_node"),
        ]
        ctx = create_context("0", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "farewell"

    @pytest.mark.asyncio
    async def test_matches_all_menu_options(self, matcher, mock_config_loader):
        """Test matching all standard menu options 1-6."""
        configs = [
            create_config("1", "option_1"),
            create_config("2", "option_2"),
            create_config("3", "option_3"),
            create_config("4", "option_4"),
            create_config("5", "option_5"),
            create_config("6", "option_6"),
        ]
        mock_config_loader.get_configs_by_type.return_value = configs

        for i in range(1, 7):
            ctx = create_context(str(i), mock_config_loader, awaiting="menu_selection")
            result = await matcher.matches(ctx)
            assert result is not None
            assert result.config.target_intent == f"option_{i}"

    @pytest.mark.asyncio
    async def test_no_match_for_invalid_number(self, matcher, mock_config_loader):
        """Test no match for number not in menu configs."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "option_1"),
            create_config("2", "option_2"),
        ]
        ctx = create_context("9", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is None


class TestMenuOptionMatcherEmojiNumbers:
    """Tests for emoji number conversion."""

    def test_emoji_map_contains_all_options(self):
        """Test that EMOJI_MAP contains all expected options."""
        assert "1\ufe0f\u20e3" in EMOJI_MAP
        assert "2\ufe0f\u20e3" in EMOJI_MAP
        assert "3\ufe0f\u20e3" in EMOJI_MAP
        assert "4\ufe0f\u20e3" in EMOJI_MAP
        assert "5\ufe0f\u20e3" in EMOJI_MAP
        assert "6\ufe0f\u20e3" in EMOJI_MAP
        assert "0\ufe0f\u20e3" in EMOJI_MAP

    @pytest.mark.asyncio
    async def test_matches_emoji_1(self, matcher, mock_config_loader):
        """Test matching emoji number 1."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "debt_query", "debt_manager"),
        ]
        ctx = create_context("1\ufe0f\u20e3", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "debt_query"

    @pytest.mark.asyncio
    async def test_matches_emoji_0(self, matcher, mock_config_loader):
        """Test matching emoji number 0."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("0", "farewell"),
        ]
        ctx = create_context("0\ufe0f\u20e3", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "farewell"

    @pytest.mark.asyncio
    async def test_matches_all_emoji_numbers(self, matcher, mock_config_loader):
        """Test matching all emoji numbers."""
        configs = [
            create_config("0", "option_0"),
            create_config("1", "option_1"),
            create_config("2", "option_2"),
            create_config("3", "option_3"),
            create_config("4", "option_4"),
            create_config("5", "option_5"),
            create_config("6", "option_6"),
        ]
        mock_config_loader.get_configs_by_type.return_value = configs

        for digit, emoji in EMOJI_MAP.items():
            ctx = create_context(digit, mock_config_loader, awaiting="menu_selection")
            result = await matcher.matches(ctx)
            assert result is not None, f"Failed for emoji {emoji}"


class TestMenuOptionMatcherEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_no_configs(self, matcher, mock_config_loader):
        """Test no match when no menu_option configs exist."""
        mock_config_loader.get_configs_by_type.return_value = []
        ctx = create_context("1", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self, matcher, mock_config_loader):
        """Test that whitespace is stripped from message."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "option_1"),
        ]
        ctx = create_context("  1  ", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_no_match_for_text(self, matcher, mock_config_loader):
        """Test no match for text input in menu context."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "option_1"),
        ]
        ctx = create_context("quiero ver mi deuda", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_for_multi_digit(self, matcher, mock_config_loader):
        """Test no match for multi-digit numbers."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("1", "option_1"),
        ]
        ctx = create_context("12", mock_config_loader, awaiting="menu_selection")

        result = await matcher.matches(ctx)

        assert result is None
