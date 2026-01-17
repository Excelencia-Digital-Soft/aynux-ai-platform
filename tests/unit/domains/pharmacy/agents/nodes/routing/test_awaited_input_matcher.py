"""Tests for AwaitedInputMatcher - Awaited input validation for routing."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.domains.pharmacy.agents.nodes.routing.matchers.awaited_input import (
    AwaitedInputMatcher,
)
from app.domains.pharmacy.agents.nodes.routing.matchers.base import MatchContext

# Patch path for AmountValidator (imported inside _extract_amount method)
AMOUNT_VALIDATOR_PATCH = "app.domains.pharmacy.agents.utils.payment.AmountValidator"


@dataclass
class MockAwaitingTypeConfigDTO:
    """Mock AwaitingTypeConfigDTO for testing."""

    id: str
    awaiting_type: str
    target_node: str
    valid_response_intents: tuple[str, ...]
    validation_pattern: str | None
    priority: int
    display_name: str | None


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def matcher(mock_db) -> AwaitedInputMatcher:
    """Create an AwaitedInputMatcher instance."""
    return AwaitedInputMatcher(mock_db)


@pytest.fixture
def mock_config_loader() -> MagicMock:
    """Create a mock config loader."""
    loader = MagicMock()
    loader.escape_intents = frozenset()
    return loader


@pytest.fixture
def org_id() -> UUID:
    """Create a test organization UUID."""
    return UUID("12345678-1234-5678-1234-567812345678")


def create_awaiting_config(
    awaiting_type: str,
    target_node: str,
    valid_intents: list[str] | None = None,
    validation_pattern: str | None = None,
) -> MockAwaitingTypeConfigDTO:
    """Helper to create mock awaiting config."""
    return MockAwaitingTypeConfigDTO(
        id="test-id",
        awaiting_type=awaiting_type,
        target_node=target_node,
        valid_response_intents=tuple(valid_intents or []),
        validation_pattern=validation_pattern,
        priority=0,
        display_name=None,
    )


def create_context(
    message: str,
    config_loader: MagicMock,
    awaiting: str | None = None,
    org_id: UUID | None = None,
) -> MatchContext:
    """Helper to create match context."""
    state = {}
    if org_id:
        state["organization_id"] = org_id
    return MatchContext(
        message=message,
        message_lower=message.strip().lower(),
        state=state,
        config_loader=config_loader,
        awaiting=awaiting,
        current_intent=None,
    )


class TestAwaitedInputMatcherPriority:
    """Tests for matcher priority."""

    def test_priority_is_0(self, matcher):
        """Test that priority is 0 (highest)."""
        assert matcher.priority == 0


class TestAwaitedInputMatcherNoAwaiting:
    """Tests when not awaiting input."""

    @pytest.mark.asyncio
    async def test_no_match_when_not_awaiting(self, matcher, mock_config_loader):
        """Test no match when not awaiting any input."""
        ctx = create_context("hello", mock_config_loader, awaiting=None)

        result = await matcher.matches(ctx)

        assert result is None


class TestAwaitedInputMatcherAmountValidation:
    """Tests for amount-related awaiting states."""

    @pytest.mark.asyncio
    async def test_matches_amount_in_amount_awaiting(self, matcher, mock_config_loader):
        """Test matching amount when awaiting 'amount'."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("1500", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 1500.0

            result = await matcher.matches(ctx)

            assert result is not None
            assert result.match_type == "awaited_input"

    @pytest.mark.asyncio
    async def test_matches_amount_in_pay_debt_action(self, matcher, mock_config_loader, org_id):
        """Test matching amount in pay_debt_action routes to payment_processor."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("2500", mock_config_loader, awaiting="pay_debt_action", org_id=org_id)

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 2500.0

            result = await matcher.matches(ctx)

            assert result is not None
            assert result.handler_key == "awaited_input_amount"
            assert result.metadata["next_node"] == "payment_processor"
            assert result.metadata["amount"] == 2500.0

    @pytest.mark.asyncio
    async def test_matches_natural_language_amount(self, matcher, mock_config_loader):
        """Test matching natural language amount."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("quiero pagar 15 mil pesos", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 15000.0

            result = await matcher.matches(ctx)

            assert result is not None

    @pytest.mark.asyncio
    async def test_no_match_for_zero_amount(self, matcher, mock_config_loader):
        """Test no match when extracted amount is 0."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("0", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 0.0

            result = await matcher.matches(ctx)

            # Amount of 0 should not be valid
            assert result is None

    @pytest.mark.asyncio
    async def test_no_match_for_negative_amount(self, matcher, mock_config_loader):
        """Test no match when extracted amount is negative."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("-100", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = -100.0

            result = await matcher.matches(ctx)

            assert result is None

    @pytest.mark.asyncio
    async def test_no_match_when_no_amount_extracted(self, matcher, mock_config_loader):
        """Test no match when no amount can be extracted."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("hello", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = None

            result = await matcher.matches(ctx)

            assert result is None


class TestAwaitedInputMatcherValidationPattern:
    """Tests for validation pattern matching."""

    @pytest.mark.asyncio
    async def test_matches_validation_pattern(self, matcher, mock_config_loader, org_id):
        """Test matching via regex validation pattern."""
        config = create_awaiting_config(
            "dni",
            "auth_plex",
            validation_pattern=r"^\d{7,8}$",
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("12345678", mock_config_loader, awaiting="dni", org_id=org_id)

        result = await matcher.matches(ctx)

        assert result is not None
        assert result.handler_key == "awaited_input"
        assert result.metadata["awaiting_type"] == "dni"

    @pytest.mark.asyncio
    async def test_no_match_invalid_pattern(self, matcher, mock_config_loader, org_id):
        """Test no match when validation pattern doesn't match."""
        config = create_awaiting_config(
            "dni",
            "auth_plex",
            validation_pattern=r"^\d{7,8}$",
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("abc123", mock_config_loader, awaiting="dni", org_id=org_id)

        result = await matcher.matches(ctx)

        assert result is None


class TestAwaitedInputMatcherKeywordMatcher:
    """Tests for valid_response_intents via KeywordMatcher."""

    @pytest.mark.asyncio
    async def test_matches_valid_response_intent(self, matcher, mock_config_loader, org_id):
        """Test matching via KeywordMatcher for valid_response_intents."""
        config = create_awaiting_config(
            "own_or_other",
            "account_switcher",
            valid_intents=["own_debt", "other_debt"],
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("mi propia deuda", mock_config_loader, awaiting="own_or_other", org_id=org_id)

        with patch(
            "app.domains.pharmacy.agents.nodes.routing.matchers.awaited_input.KeywordMatcher"
        ) as MockKeywordMatcher:
            MockKeywordMatcher.matches_any_of = AsyncMock(return_value="own_debt")

            result = await matcher.matches(ctx)

            assert result is not None
            MockKeywordMatcher.matches_any_of.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_match_when_no_intent_matches(self, matcher, mock_config_loader, org_id):
        """Test no match when KeywordMatcher returns None."""
        config = create_awaiting_config(
            "own_or_other",
            "account_switcher",
            valid_intents=["own_debt", "other_debt"],
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("random text", mock_config_loader, awaiting="own_or_other", org_id=org_id)

        with patch(
            "app.domains.pharmacy.agents.nodes.routing.matchers.awaited_input.KeywordMatcher"
        ) as MockKeywordMatcher:
            MockKeywordMatcher.matches_any_of = AsyncMock(return_value=None)

            result = await matcher.matches(ctx)

            assert result is None

    @pytest.mark.asyncio
    async def test_skips_keyword_check_without_org_id(self, matcher, mock_config_loader):
        """Test that keyword check is skipped without organization_id."""
        config = create_awaiting_config(
            "own_or_other",
            "account_switcher",
            valid_intents=["own_debt"],
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("mi deuda", mock_config_loader, awaiting="own_or_other", org_id=None)

        with patch(
            "app.domains.pharmacy.agents.nodes.routing.matchers.awaited_input.KeywordMatcher"
        ) as MockKeywordMatcher:
            MockKeywordMatcher.matches_any_of = AsyncMock()

            result = await matcher.matches(ctx)

            # Should not call KeywordMatcher without org_id
            MockKeywordMatcher.matches_any_of.assert_not_called()


class TestAwaitedInputMatcherNoConfig:
    """Tests when no awaiting config exists."""

    @pytest.mark.asyncio
    async def test_no_match_when_no_config(self, matcher, mock_config_loader, org_id):
        """Test no match when no awaiting type config exists."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("random input", mock_config_loader, awaiting="unknown_type", org_id=org_id)

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = None

            result = await matcher.matches(ctx)

            assert result is None


class TestAwaitedInputMatcherOrganizationId:
    """Tests for organization_id extraction."""

    @pytest.mark.asyncio
    async def test_extracts_uuid_org_id(self, matcher, mock_config_loader):
        """Test extracting UUID organization_id from state."""
        mock_config_loader.get_awaiting_config.return_value = None
        org_uuid = UUID("12345678-1234-5678-1234-567812345678")
        ctx = create_context("1500", mock_config_loader, awaiting="amount", org_id=org_uuid)

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 1500.0

            result = await matcher.matches(ctx)

            assert result is not None

    @pytest.mark.asyncio
    async def test_handles_string_org_id(self, matcher, mock_config_loader):
        """Test handling string organization_id in state."""
        mock_config_loader.get_awaiting_config.return_value = None
        state = {"organization_id": "12345678-1234-5678-1234-567812345678"}
        ctx = MatchContext(
            message="1500",
            message_lower="1500",
            state=state,
            config_loader=mock_config_loader,
            awaiting="amount",
            current_intent=None,
        )

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 1500.0

            result = await matcher.matches(ctx)

            assert result is not None

    @pytest.mark.asyncio
    async def test_handles_invalid_org_id(self, matcher, mock_config_loader):
        """Test handling invalid organization_id in state."""
        mock_config_loader.get_awaiting_config.return_value = None
        state = {"organization_id": "not-a-valid-uuid"}
        ctx = MatchContext(
            message="1500",
            message_lower="1500",
            state=state,
            config_loader=mock_config_loader,
            awaiting="amount",
            current_intent=None,
        )

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.return_value = 1500.0

            result = await matcher.matches(ctx)

            # Should still work for amount validation (doesn't need org_id)
            assert result is not None


class TestAwaitedInputMatcherEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_empty_valid_intents(self, matcher, mock_config_loader, org_id):
        """Test handling empty valid_response_intents list."""
        config = create_awaiting_config(
            "custom_type",
            "custom_node",
            valid_intents=[],
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("input", mock_config_loader, awaiting="custom_type", org_id=org_id)

        result = await matcher.matches(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_both_pattern_and_intents(self, matcher, mock_config_loader, org_id):
        """Test config with both validation_pattern and valid_response_intents."""
        config = create_awaiting_config(
            "hybrid",
            "hybrid_node",
            valid_intents=["intent1"],
            validation_pattern=r"^\d+$",
        )
        mock_config_loader.get_awaiting_config.return_value = config
        ctx = create_context("12345", mock_config_loader, awaiting="hybrid", org_id=org_id)

        # Pattern should match first
        result = await matcher.matches(ctx)

        assert result is not None

    @pytest.mark.asyncio
    async def test_amount_extraction_error_handled(self, matcher, mock_config_loader):
        """Test that errors in amount extraction are handled gracefully."""
        mock_config_loader.get_awaiting_config.return_value = None
        ctx = create_context("bad input", mock_config_loader, awaiting="amount")

        with patch(AMOUNT_VALIDATOR_PATCH) as MockValidator:
            MockValidator.extract_amount.side_effect = Exception("Parse error")

            # Should not raise, should return None
            result = await matcher.matches(ctx)

            assert result is None
