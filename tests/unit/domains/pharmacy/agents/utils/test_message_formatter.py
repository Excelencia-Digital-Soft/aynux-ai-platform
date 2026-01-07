"""Tests for MessageFormatter utility."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.domains.pharmacy.agents.utils.message_formatter import MessageFormatter


class TestMessageFormatter:
    """Test suite for MessageFormatter."""

    @pytest.fixture
    def formatter(self) -> MessageFormatter:
        """Create formatter instance for testing."""
        return MessageFormatter()

    class TestFormatResultMessages:
        """Tests for format_result_messages method."""

        def test_converts_dict_assistant_message(self):
            """Test converting assistant dict message."""
            messages = [{"role": "assistant", "content": "Hello!"}]
            result = MessageFormatter.format_result_messages(messages)

            assert len(result) == 1
            assert isinstance(result[0], AIMessage)
            assert result[0].content == "Hello!"

        def test_converts_dict_user_message(self):
            """Test converting user dict message."""
            messages = [{"role": "user", "content": "Hi there"}]
            result = MessageFormatter.format_result_messages(messages)

            assert len(result) == 1
            assert isinstance(result[0], HumanMessage)
            assert result[0].content == "Hi there"

        def test_preserves_existing_message_objects(self):
            """Test that existing message objects are preserved."""
            original_ai = AIMessage(content="AI response")
            original_human = HumanMessage(content="Human input")
            messages = [original_ai, original_human]

            result = MessageFormatter.format_result_messages(messages)

            assert len(result) == 2
            assert result[0] is original_ai
            assert result[1] is original_human

        def test_handles_mixed_messages(self):
            """Test handling mix of dict and object messages."""
            messages = [
                {"role": "user", "content": "Question"},
                AIMessage(content="Answer"),
                {"role": "assistant", "content": "Follow-up"},
            ]
            result = MessageFormatter.format_result_messages(messages)

            assert len(result) == 3
            assert isinstance(result[0], HumanMessage)
            assert isinstance(result[1], AIMessage)
            assert isinstance(result[2], AIMessage)

        def test_handles_empty_list(self):
            """Test handling empty message list."""
            result = MessageFormatter.format_result_messages([])
            assert result == []

    class TestCreateMessages:
        """Tests for message creation methods."""

        def test_create_assistant_message(self):
            """Test creating an assistant message."""
            message = MessageFormatter.create_assistant_message("Hello!")
            assert isinstance(message, AIMessage)
            assert message.content == "Hello!"

        def test_create_human_message(self):
            """Test creating a human message."""
            message = MessageFormatter.create_human_message("Hi!")
            assert isinstance(message, HumanMessage)
            assert message.content == "Hi!"

    class TestToDict:
        """Tests for to_dict method."""

        def test_converts_ai_message_to_dict(self):
            """Test converting AIMessage to dict."""
            message = AIMessage(content="Hello!")
            result = MessageFormatter.to_dict(message)

            assert result == {"role": "assistant", "content": "Hello!"}

        def test_converts_human_message_to_dict(self):
            """Test converting HumanMessage to dict."""
            message = HumanMessage(content="Hi there")
            result = MessageFormatter.to_dict(message)

            assert result == {"role": "user", "content": "Hi there"}

    class TestFormatErrorResponse:
        """Tests for format_error_response method."""

        def test_formats_exception(self):
            """Test formatting an exception."""
            error = ValueError("Something went wrong")
            result = MessageFormatter.format_error_response(error)

            assert "messages" in result
            assert "error" in result
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert "problema" in result["messages"][0].content.lower()

        def test_formats_string_error(self):
            """Test formatting a string error."""
            result = MessageFormatter.format_error_response("Custom error")

            assert "messages" in result
            assert result["error"] == "Custom error"
