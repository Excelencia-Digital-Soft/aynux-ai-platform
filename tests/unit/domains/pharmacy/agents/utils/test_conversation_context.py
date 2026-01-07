"""Tests for ConversationContextBuilder utility."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.domains.pharmacy.agents.utils.conversation_context import ConversationContextBuilder


class TestConversationContextBuilder:
    """Test suite for ConversationContextBuilder."""

    @pytest.fixture
    def builder(self) -> ConversationContextBuilder:
        """Create builder instance for testing."""
        return ConversationContextBuilder()

    class TestFormatRecentHistory:
        """Tests for format_recent_history method."""

        @pytest.fixture
        def builder(self) -> ConversationContextBuilder:
            return ConversationContextBuilder()

        def test_formats_conversation_history(self, builder: ConversationContextBuilder):
            """Test formatting a conversation history."""
            state = {
                "messages": [
                    HumanMessage(content="Hola"),
                    AIMessage(content="¡Hola! ¿En qué puedo ayudarte?"),
                    HumanMessage(content="Quiero ver mi deuda"),
                    AIMessage(content="Tu deuda es de $1000"),
                    HumanMessage(content="Current message"),  # Will be excluded
                ]
            }
            result = builder.format_recent_history(state)

            assert "Usuario: Hola" in result
            assert "Asistente: ¡Hola!" in result
            assert "Usuario: Quiero ver mi deuda" in result
            assert "Asistente: Tu deuda" in result
            assert "Current message" not in result

        def test_returns_empty_for_single_message(self, builder: ConversationContextBuilder):
            """Test returning empty string for single message."""
            state = {"messages": [HumanMessage(content="Only message")]}
            result = builder.format_recent_history(state)
            assert result == ""

        def test_returns_empty_for_no_messages(self, builder: ConversationContextBuilder):
            """Test returning empty string for no messages."""
            assert builder.format_recent_history({}) == ""
            assert builder.format_recent_history({"messages": []}) == ""

        def test_truncates_long_responses(self, builder: ConversationContextBuilder):
            """Test truncating long assistant responses."""
            long_response = "A" * 200
            state = {
                "messages": [
                    HumanMessage(content="Question"),
                    AIMessage(content=long_response),
                    HumanMessage(content="Current"),
                ]
            }
            result = builder.format_recent_history(state, max_response_length=50)

            assert "..." in result
            assert len(result.split("Asistente: ")[1].split("\n")[0]) <= 53  # 50 + "..."

        def test_respects_max_turns(self, builder: ConversationContextBuilder):
            """Test respecting max_turns parameter."""
            state = {
                "messages": [
                    HumanMessage(content="Turn 1"),
                    AIMessage(content="Response 1"),
                    HumanMessage(content="Turn 2"),
                    AIMessage(content="Response 2"),
                    HumanMessage(content="Turn 3"),
                    AIMessage(content="Response 3"),
                    HumanMessage(content="Current"),
                ]
            }
            result = builder.format_recent_history(state, max_turns=2)

            assert "Turn 2" in result
            assert "Turn 3" in result
            assert "Turn 1" not in result

    class TestFormatMessagesList:
        """Tests for format_messages_list method."""

        @pytest.fixture
        def builder(self) -> ConversationContextBuilder:
            return ConversationContextBuilder()

        def test_formats_human_message(self, builder: ConversationContextBuilder):
            """Test formatting HumanMessage."""
            messages = [HumanMessage(content="Hello")]
            result = builder.format_messages_list(messages)

            assert len(result) == 1
            assert result[0] == {"role": "user", "content": "Hello"}

        def test_formats_ai_message(self, builder: ConversationContextBuilder):
            """Test formatting AIMessage."""
            messages = [AIMessage(content="Hi there")]
            result = builder.format_messages_list(messages)

            assert len(result) == 1
            assert result[0] == {"role": "assistant", "content": "Hi there"}

        def test_formats_dict_message(self, builder: ConversationContextBuilder):
            """Test formatting dict message."""
            messages = [{"role": "user", "content": "Test"}]
            result = builder.format_messages_list(messages)

            assert len(result) == 1
            assert result[0] == {"role": "user", "content": "Test"}

        def test_truncates_long_content(self, builder: ConversationContextBuilder):
            """Test truncating long content."""
            messages = [HumanMessage(content="A" * 200)]
            result = builder.format_messages_list(messages, max_length=50)

            assert len(result[0]["content"]) == 53  # 50 + "..."
            assert result[0]["content"].endswith("...")

    class TestBuildContextDict:
        """Tests for build_context_dict method."""

        @pytest.fixture
        def builder(self) -> ConversationContextBuilder:
            return ConversationContextBuilder()

        def test_builds_basic_context(self, builder: ConversationContextBuilder):
            """Test building basic context dict."""
            state = {
                "customer_identified": True,
                "customer_name": "Juan",
                "has_debt": True,
                "debt_status": "pending",
            }
            result = builder.build_context_dict(state, include_history=False)

            assert result["customer_identified"] is True
            assert result["customer_name"] == "Juan"
            assert result["has_debt"] is True
            assert result["debt_status"] == "pending"
            assert "conversation_history" not in result

        def test_includes_history_when_requested(self, builder: ConversationContextBuilder):
            """Test including conversation history."""
            state = {
                "messages": [
                    HumanMessage(content="Hello"),
                    AIMessage(content="Hi"),
                    HumanMessage(content="Current"),
                ],
                "customer_identified": True,
            }
            result = builder.build_context_dict(state, include_history=True)

            assert "conversation_history" in result
            assert "Hello" in result["conversation_history"]

        def test_uses_defaults_for_missing_values(self, builder: ConversationContextBuilder):
            """Test using defaults for missing state values."""
            result = builder.build_context_dict({}, include_history=False)

            assert result["customer_identified"] is False
            assert result["customer_name"] == "Cliente"
            assert result["has_debt"] is False
            assert result["debt_status"] is None
