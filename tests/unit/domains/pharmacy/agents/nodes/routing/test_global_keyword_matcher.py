"""Tests for GlobalKeywordMatcher - Global keyword matching for routing."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext
from app.domains.pharmacy.agents.nodes.routing.matchers.global_keyword import (
    GlobalKeywordMatcher,
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
def matcher() -> GlobalKeywordMatcher:
    """Create a GlobalKeywordMatcher instance."""
    return GlobalKeywordMatcher()


@pytest.fixture
def mock_config_loader() -> MagicMock:
    """Create a mock config loader."""
    loader = MagicMock()
    loader.escape_intents = frozenset({"cancel_flow", "farewell", "show_menu"})
    return loader


def create_config(
    trigger: str,
    intent: str,
    node: str | None = None,
    aliases: list[str] | None = None,
) -> MockRoutingConfigDTO:
    """Helper to create mock config."""
    metadata = {"aliases": aliases} if aliases else None
    return MockRoutingConfigDTO(
        id="test-id",
        config_type="global_keyword",
        trigger_value=trigger,
        target_intent=intent,
        target_node=node,
        priority=100,
        requires_auth=False,
        clears_context=False,
        metadata=metadata,
        display_name=None,
    )


def create_context(
    message: str,
    config_loader: MagicMock,
    awaiting: str | None = None,
    current_intent: str | None = None,
) -> MatchContext:
    """Helper to create match context."""
    return MatchContext(
        message=message,
        message_lower=message.strip().lower(),
        state={},
        config_loader=config_loader,
        awaiting=awaiting,
        current_intent=current_intent,
    )


class TestGlobalKeywordMatcherPriority:
    """Tests for matcher priority."""

    def test_priority_is_100(self, matcher):
        """Test that priority is 100."""
        assert matcher.priority == 100


class TestGlobalKeywordMatcherMatches:
    """Tests for matches method."""

    @pytest.mark.asyncio
    async def test_matches_exact_keyword(self, matcher, mock_config_loader):
        """Test matching exact keyword."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu", "main_menu_node"),
        ]
        ctx = create_context("menu", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.match_type == "global_keyword"
        assert result.handler_key == "global_keyword"
        assert result.config.target_intent == "show_menu"

    @pytest.mark.asyncio
    async def test_matches_keyword_with_trailing_text(self, matcher, mock_config_loader):
        """Test matching keyword followed by space and text."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
        ]
        ctx = create_context("menu principal", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "show_menu"

    @pytest.mark.asyncio
    async def test_matches_alias(self, matcher, mock_config_loader):
        """Test matching keyword alias."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("cancelar", "cancel_flow", aliases=["cancela", "anular"]),
        ]
        ctx = create_context("cancela", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "cancel_flow"

    @pytest.mark.asyncio
    async def test_matches_alias_with_trailing_text(self, matcher, mock_config_loader):
        """Test matching alias followed by space and text."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("salir", "farewell", aliases=["chau", "adios"]),
        ]
        ctx = create_context("chau gracias", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "farewell"

    @pytest.mark.asyncio
    async def test_no_match_when_keyword_is_substring(self, matcher, mock_config_loader):
        """Test no match when keyword is substring of word."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
        ]
        ctx = create_context("menuitem", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_when_no_configs(self, matcher, mock_config_loader):
        """Test no match when no global_keyword configs exist."""
        mock_config_loader.get_configs_by_type.return_value = []
        ctx = create_context("menu", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_for_unrelated_message(self, matcher, mock_config_loader):
        """Test no match for unrelated message."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
            create_config("cancelar", "cancel_flow"),
        ]
        ctx = create_context("quiero ver mi deuda", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, matcher, mock_config_loader):
        """Test that matching is case-insensitive."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
        ]
        ctx = create_context("MENU", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_blocks_non_escape_when_awaiting(self, matcher, mock_config_loader):
        """Test that non-escape keywords are blocked when awaiting input."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("otra cuenta", "switch_account"),  # Not an escape intent
        ]
        ctx = create_context("otra cuenta", mock_config_loader, awaiting="own_or_other")

        result = await matcher.matches(ctx)

        assert result is None  # Should be blocked

    @pytest.mark.asyncio
    async def test_allows_escape_when_awaiting(self, matcher, mock_config_loader):
        """Test that escape keywords are allowed when awaiting input."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),  # Is an escape intent
        ]
        ctx = create_context("menu", mock_config_loader, awaiting="dni")

        result = await matcher.matches(ctx)

        assert result is not None  # Should be allowed

    @pytest.mark.asyncio
    async def test_escape_intents_checked_against_config(self, matcher, mock_config_loader):
        """Test that escape intents are checked from config loader."""
        mock_config_loader.escape_intents = frozenset({"cancel_flow"})
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("cancelar", "cancel_flow"),
            create_config("menu", "show_menu"),  # Not in escape_intents
        ]

        # Test cancel (escape) is allowed
        ctx1 = create_context("cancelar", mock_config_loader, awaiting="amount")
        result1 = await matcher.matches(ctx1)
        assert result1 is not None

        # Test menu (non-escape) is blocked
        ctx2 = create_context("menu", mock_config_loader, awaiting="amount")
        result2 = await matcher.matches(ctx2)
        assert result2 is None


class TestGlobalKeywordMatcherEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_empty_message(self, matcher, mock_config_loader):
        """Test with empty message."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
        ]
        ctx = create_context("", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_only_message(self, matcher, mock_config_loader):
        """Test with whitespace-only message."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu"),
        ]
        ctx = create_context("   ", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_aliases_list(self, matcher, mock_config_loader):
        """Test config with empty aliases list."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu", aliases=[]),
        ]
        ctx = create_context("menu", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_first_matching_config_wins(self, matcher, mock_config_loader):
        """Test that first matching config is returned."""
        mock_config_loader.get_configs_by_type.return_value = [
            create_config("menu", "show_menu_1"),
            create_config("menu", "show_menu_2"),
        ]
        ctx = create_context("menu", mock_config_loader)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.config.target_intent == "show_menu_1"
