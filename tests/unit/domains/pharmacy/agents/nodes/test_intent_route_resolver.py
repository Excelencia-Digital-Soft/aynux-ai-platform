"""Tests for IntentRouteResolver - Intent analysis to routing decisions."""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.domains.pharmacy.agents.nodes.intent_route_resolver import IntentRouteResolver


# Test fixtures and mocks
@dataclass
class MockIntentResult:
    """Mock PharmacyIntentResult for testing."""

    intent: str
    confidence: float
    is_out_of_scope: bool = False
    suggested_response: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    method: str = "hybrid"
    analysis: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockMessage:
    """Mock message object for testing."""

    content: str
    type: str


@dataclass
class MockRoutingConfig:
    """Mock routing config DTO for testing."""

    trigger_value: str
    target_node: str | None
    requires_auth: bool


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def resolver(mock_db):
    """Create an IntentRouteResolver instance with mocked db."""
    return IntentRouteResolver(mock_db)


@pytest.fixture
def org_id():
    """Create a test organization UUID."""
    return UUID("12345678-1234-5678-1234-567812345678")


class TestIntentRouteResolverInit:
    """Tests for IntentRouteResolver initialization."""

    def test_init_sets_db(self, mock_db):
        """Test that __init__ sets the database session."""
        resolver = IntentRouteResolver(mock_db)
        assert resolver._db is mock_db

    def test_init_sets_none_analyzer(self, mock_db):
        """Test that analyzer starts as None (lazy initialization)."""
        resolver = IntentRouteResolver(mock_db)
        assert resolver._analyzer is None

    def test_init_sets_none_mappings(self, mock_db):
        """Test that intent mappings start as None."""
        resolver = IntentRouteResolver(mock_db)
        assert resolver._intent_node_mapping is None


class TestGetAnalyzer:
    """Tests for _get_analyzer method."""

    def test_creates_analyzer_on_first_call(self, resolver):
        """Test that analyzer is created on first call."""
        with patch(
            "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
        ) as mock_factory:
            mock_analyzer = MagicMock()
            mock_factory.return_value = mock_analyzer

            result = resolver._get_analyzer()

            assert result is mock_analyzer
            mock_factory.assert_called_once_with(
                db=resolver._db,
                use_llm_fallback=True,
            )

    def test_returns_cached_analyzer_on_subsequent_calls(self, resolver):
        """Test that analyzer is cached after first creation."""
        with patch(
            "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
        ) as mock_factory:
            mock_analyzer = MagicMock()
            mock_factory.return_value = mock_analyzer

            # First call
            result1 = resolver._get_analyzer()
            # Second call
            result2 = resolver._get_analyzer()

            assert result1 is result2
            assert mock_factory.call_count == 1


class TestLoadIntentMappings:
    """Tests for _load_intent_mappings method."""

    @pytest.mark.asyncio
    async def test_loads_mappings_from_cache(self, resolver, org_id):
        """Test that mappings are loaded from routing config cache."""
        mock_configs = {
            "intent_node_mapping": [
                MockRoutingConfig("debt_query", "debt_manager", False),
                MockRoutingConfig("payment", "payment_node", True),
            ]
        }

        with patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache:
            mock_cache.get_configs = AsyncMock(return_value=mock_configs)

            await resolver._load_intent_mappings(org_id)

            mock_cache.get_configs.assert_called_once_with(resolver._db, org_id, "pharmacy")
            assert resolver._intent_node_mapping == {
                "debt_query": ("debt_manager", False),
                "payment": ("payment_node", True),
            }

    @pytest.mark.asyncio
    async def test_skips_loading_if_already_loaded(self, resolver, org_id):
        """Test that mappings are not reloaded if already present."""
        resolver._intent_node_mapping = {"existing": ("node", False)}

        with patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache:
            mock_cache.get_configs = AsyncMock()

            await resolver._load_intent_mappings(org_id)

            mock_cache.get_configs.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_configs(self, resolver, org_id):
        """Test handling when no intent_node_mapping configs exist."""
        with patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache:
            mock_cache.get_configs = AsyncMock(return_value={})

            await resolver._load_intent_mappings(org_id)

            assert resolver._intent_node_mapping == {}

    @pytest.mark.asyncio
    async def test_uses_default_node_when_target_is_none(self, resolver, org_id):
        """Test that main_menu_node is used when target_node is None."""
        mock_configs = {
            "intent_node_mapping": [
                MockRoutingConfig("greeting", None, False),
            ]
        }

        with patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache:
            mock_cache.get_configs = AsyncMock(return_value=mock_configs)

            await resolver._load_intent_mappings(org_id)

            assert resolver._intent_node_mapping["greeting"] == ("main_menu_node", False)


class TestBuildContext:
    """Tests for _build_context method."""

    def test_builds_context_for_authenticated_user_with_debt(self, resolver):
        """Test context building for authenticated user with debt."""
        state = {
            "is_authenticated": True,
            "awaiting_payment_confirmation": True,
            "total_debt": 1500.50,
            "messages": [],
        }

        context = resolver._build_context(state)

        assert context["customer_identified"] is True
        assert context["awaiting_confirmation"] is True
        assert context["debt_status"] == "has_debt"
        assert context["conversation_history"] == ""

    def test_builds_context_for_unauthenticated_user_no_debt(self, resolver):
        """Test context building for unauthenticated user without debt."""
        state = {
            "is_authenticated": False,
            "awaiting_payment_confirmation": False,
            "total_debt": 0,
            "messages": [],
        }

        context = resolver._build_context(state)

        assert context["customer_identified"] is False
        assert context["awaiting_confirmation"] is False
        assert context["debt_status"] == "no_debt"

    def test_handles_missing_state_keys(self, resolver):
        """Test context building with minimal state."""
        state = {}

        context = resolver._build_context(state)

        assert context["customer_identified"] is False
        assert context["awaiting_confirmation"] is False
        assert context["debt_status"] == "no_debt"
        assert context["conversation_history"] == ""

    def test_handles_none_total_debt(self, resolver):
        """Test context building when total_debt is None."""
        state = {"total_debt": None}

        context = resolver._build_context(state)

        assert context["debt_status"] == "no_debt"

    def test_handles_negative_debt(self, resolver):
        """Test context building with negative debt (credit)."""
        state = {"total_debt": -100}

        context = resolver._build_context(state)

        assert context["debt_status"] == "no_debt"


class TestGetRecentMessages:
    """Tests for _get_recent_messages method."""

    def test_returns_empty_string_for_no_messages(self, resolver):
        """Test that empty string is returned when no messages exist."""
        state = {"messages": []}

        result = resolver._get_recent_messages(state)

        assert result == ""

    def test_returns_empty_string_for_missing_messages_key(self, resolver):
        """Test that empty string is returned when messages key is missing."""
        state = {}

        result = resolver._get_recent_messages(state)

        assert result == ""

    def test_formats_human_messages(self, resolver):
        """Test that human messages are formatted correctly."""
        state = {
            "messages": [
                MockMessage("Hola", "human"),
            ]
        }

        result = resolver._get_recent_messages(state)

        assert result == "Usuario: Hola"

    def test_formats_bot_messages(self, resolver):
        """Test that bot messages are formatted correctly."""
        state = {
            "messages": [
                MockMessage("Bienvenido", "ai"),
            ]
        }

        result = resolver._get_recent_messages(state)

        assert result == "Bot: Bienvenido"

    def test_formats_multiple_messages(self, resolver):
        """Test formatting of multiple messages."""
        state = {
            "messages": [
                MockMessage("Hola", "human"),
                MockMessage("Bienvenido", "ai"),
                MockMessage("Quiero ver mi deuda", "human"),
            ]
        }

        result = resolver._get_recent_messages(state)

        expected = "Usuario: Hola\nBot: Bienvenido\nUsuario: Quiero ver mi deuda"
        assert result == expected

    def test_respects_limit_parameter(self, resolver):
        """Test that limit parameter is respected."""
        state = {
            "messages": [
                MockMessage("Mensaje 1", "human"),
                MockMessage("Mensaje 2", "ai"),
                MockMessage("Mensaje 3", "human"),
                MockMessage("Mensaje 4", "ai"),
                MockMessage("Mensaje 5", "human"),
            ]
        }

        result = resolver._get_recent_messages(state, limit=2)

        expected = "Bot: Mensaje 4\nUsuario: Mensaje 5"
        assert result == expected

    def test_skips_messages_without_content_attribute(self, resolver):
        """Test that messages without content attribute are skipped."""
        state = {
            "messages": [
                MockMessage("Valid message", "human"),
                {"invalid": "object"},  # No content or type attribute
            ]
        }

        result = resolver._get_recent_messages(state)

        assert result == "Usuario: Valid message"


class TestMapIntentToRoute:
    """Tests for _map_intent_to_route method."""

    def test_maps_known_intent_to_configured_node(self, resolver):
        """Test mapping a known intent to its configured node."""
        resolver._intent_node_mapping = {
            "debt_query": ("debt_manager", False),
        }
        result = MockIntentResult(intent="debt_query", confidence=0.9)
        state = {"intent": "previous_intent", "is_authenticated": True}

        route = resolver._map_intent_to_route(result, state)

        assert route["intent"] == "debt_query"
        assert route["previous_intent"] == "previous_intent"
        assert route["next_node"] == "debt_manager"
        assert route["awaiting_input"] is None

    def test_maps_unknown_intent_to_main_menu(self, resolver):
        """Test mapping an unknown intent to main_menu_node."""
        resolver._intent_node_mapping = {}
        result = MockIntentResult(intent="unknown_intent", confidence=0.5)
        state = {"intent": None, "is_authenticated": True}

        route = resolver._map_intent_to_route(result, state)

        assert route["intent"] == "unknown_intent"
        assert route["next_node"] == "main_menu_node"

    def test_redirects_to_auth_when_required(self, resolver):
        """Test redirection to auth_plex when auth is required but user is not authenticated."""
        resolver._intent_node_mapping = {
            "payment": ("payment_node", True),  # requires_auth=True
        }
        result = MockIntentResult(intent="payment", confidence=0.9)
        state = {"intent": "previous", "is_authenticated": False}

        route = resolver._map_intent_to_route(result, state)

        assert route["intent"] == "payment"
        assert route["next_node"] == "auth_plex"
        assert route["awaiting_input"] is None

    def test_allows_auth_required_for_authenticated_user(self, resolver):
        """Test that authenticated users can access auth-required intents."""
        resolver._intent_node_mapping = {
            "payment": ("payment_node", True),
        }
        result = MockIntentResult(intent="payment", confidence=0.9)
        state = {"intent": None, "is_authenticated": True}

        route = resolver._map_intent_to_route(result, state)

        assert route["next_node"] == "payment_node"

    def test_includes_entities_when_present(self, resolver):
        """Test that entities are included in the result when present."""
        resolver._intent_node_mapping = {
            "payment": ("payment_node", False),
        }
        result = MockIntentResult(
            intent="payment",
            confidence=0.9,
            entities={"amount": 500.00, "dni": "12345678"},
        )
        state = {"intent": None, "is_authenticated": True}

        route = resolver._map_intent_to_route(result, state)

        assert route["extracted_entities"] == {"amount": 500.00, "dni": "12345678"}

    def test_excludes_entities_when_empty(self, resolver):
        """Test that extracted_entities key is not present when entities are empty."""
        resolver._intent_node_mapping = {}
        result = MockIntentResult(intent="greeting", confidence=0.8, entities={})
        state = {"intent": None}

        route = resolver._map_intent_to_route(result, state)

        assert "extracted_entities" not in route

    def test_handles_none_mapping(self, resolver):
        """Test handling when _intent_node_mapping is None."""
        resolver._intent_node_mapping = None
        result = MockIntentResult(intent="greeting", confidence=0.8)
        state = {"intent": None}

        route = resolver._map_intent_to_route(result, state)

        assert route["next_node"] == "main_menu_node"


class TestHandleUnknownIntent:
    """Tests for _handle_unknown_intent method."""

    def test_routes_authenticated_user_to_main_menu(self, resolver):
        """Test that authenticated users are routed to main_menu_node."""
        state = {"is_authenticated": True}

        result = resolver._handle_unknown_intent(state)

        assert result["intent"] == "show_menu"
        assert result["next_node"] == "main_menu_node"

    def test_routes_unauthenticated_user_to_auth(self, resolver):
        """Test that unauthenticated users are routed to auth_plex."""
        state = {"is_authenticated": False}

        result = resolver._handle_unknown_intent(state)

        assert result["intent"] == "greeting"
        assert result["next_node"] == "auth_plex"

    def test_routes_missing_auth_to_auth(self, resolver):
        """Test that missing is_authenticated defaults to auth_plex."""
        state = {}

        result = resolver._handle_unknown_intent(state)

        assert result["intent"] == "greeting"
        assert result["next_node"] == "auth_plex"


class TestResolve:
    """Tests for resolve method - main entry point."""

    @pytest.mark.asyncio
    async def test_successful_intent_resolution(self, resolver, org_id):
        """Test successful resolution of a known intent."""
        mock_intent_result = MockIntentResult(
            intent="debt_query",
            confidence=0.9,
            is_out_of_scope=False,
            method="spacy_db",
        )

        mock_configs = {
            "intent_node_mapping": [
                MockRoutingConfig("debt_query", "debt_manager", False),
            ]
        }

        state = {
            "is_authenticated": True,
            "intent": "previous_intent",
            "messages": [],
        }

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value=mock_configs)
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            result = await resolver.resolve("Quiero ver mi deuda", state, org_id)

            assert result["intent"] == "debt_query"
            assert result["next_node"] == "debt_manager"
            assert result["previous_intent"] == "previous_intent"

    @pytest.mark.asyncio
    async def test_handles_out_of_scope_intent(self, resolver, org_id):
        """Test handling of out-of-scope intents."""
        mock_intent_result = MockIntentResult(
            intent="weather",
            confidence=0.3,
            is_out_of_scope=True,
        )

        state = {"is_authenticated": False, "messages": []}

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value={})
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            result = await resolver.resolve("What's the weather?", state, org_id)

            assert result["intent"] == "greeting"
            assert result["next_node"] == "auth_plex"

    @pytest.mark.asyncio
    async def test_handles_unknown_intent(self, resolver, org_id):
        """Test handling of unknown intents."""
        mock_intent_result = MockIntentResult(
            intent="unknown",
            confidence=0.2,
            is_out_of_scope=False,
        )

        state = {"is_authenticated": True, "messages": []}

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value={})
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            result = await resolver.resolve("asdfghjkl", state, org_id)

            assert result["intent"] == "show_menu"
            assert result["next_node"] == "main_menu_node"

    @pytest.mark.asyncio
    async def test_builds_context_for_analyzer(self, resolver, org_id):
        """Test that context is properly built and passed to analyzer."""
        mock_intent_result = MockIntentResult(intent="greeting", confidence=0.95)

        state = {
            "is_authenticated": True,
            "awaiting_payment_confirmation": True,
            "total_debt": 1000,
            "messages": [MockMessage("Hola", "human")],
        }

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value={})
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            await resolver.resolve("Hola", state, org_id)

            # Verify analyze was called with correct context
            call_kwargs = mock_analyzer.analyze.call_args.kwargs
            assert call_kwargs["context"]["customer_identified"] is True
            assert call_kwargs["context"]["awaiting_confirmation"] is True
            assert call_kwargs["context"]["debt_status"] == "has_debt"
            assert "Usuario: Hola" in call_kwargs["context"]["conversation_history"]

    @pytest.mark.asyncio
    async def test_passes_entities_from_analyzer(self, resolver, org_id):
        """Test that entities extracted by analyzer are passed through."""
        mock_intent_result = MockIntentResult(
            intent="payment",
            confidence=0.85,
            entities={"amount": 500.00},
        )

        mock_configs = {
            "intent_node_mapping": [
                MockRoutingConfig("payment", "payment_node", False),
            ]
        }

        state = {"is_authenticated": True, "messages": []}

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value=mock_configs)
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            result = await resolver.resolve("Quiero pagar 500", state, org_id)

            assert result["extracted_entities"] == {"amount": 500.00}

    @pytest.mark.asyncio
    async def test_caches_intent_mappings(self, resolver, org_id):
        """Test that intent mappings are cached across calls."""
        mock_intent_result = MockIntentResult(intent="greeting", confidence=0.9)
        mock_configs = {"intent_node_mapping": []}

        state = {"messages": []}

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value=mock_configs)
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            # Call resolve twice
            await resolver.resolve("Hola", state, org_id)
            await resolver.resolve("Gracias", state, org_id)

            # get_configs should only be called once due to caching
            assert mock_cache.get_configs.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_none_org_id(self, resolver):
        """Test resolution with None organization ID."""
        mock_intent_result = MockIntentResult(intent="greeting", confidence=0.9)

        state = {"messages": []}

        with (
            patch("app.domains.pharmacy.agents.nodes.intent_route_resolver.routing_config_cache") as mock_cache,
            patch(
                "app.domains.pharmacy.agents.nodes.intent_route_resolver.get_pharmacy_intent_analyzer"
            ) as mock_factory,
        ):
            mock_cache.get_configs = AsyncMock(return_value={})
            mock_analyzer = MagicMock()
            mock_analyzer.analyze = AsyncMock(return_value=mock_intent_result)
            mock_factory.return_value = mock_analyzer

            result = await resolver.resolve("Hola", state, None)

            assert result["intent"] == "greeting"
            mock_cache.get_configs.assert_called_once_with(resolver._db, None, "pharmacy")
