"""Tests for MessageExtractor utility."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor


class TestMessageExtractor:
    """Test suite for MessageExtractor."""

    class TestExtractLastHumanMessage:
        """Tests for extract_last_human_message method."""

        def test_extracts_from_single_human_message(self):
            """Test extracting from state with single HumanMessage."""
            state = {"messages": [HumanMessage(content="Hello")]}
            result = MessageExtractor.extract_last_human_message(state)
            assert result == "Hello"

        def test_extracts_last_from_multiple_messages(self):
            """Test extracting last HumanMessage from multiple."""
            state = {
                "messages": [
                    HumanMessage(content="First"),
                    AIMessage(content="Response"),
                    HumanMessage(content="Second"),
                    AIMessage(content="Final response"),
                ]
            }
            result = MessageExtractor.extract_last_human_message(state)
            assert result == "Second"

        def test_returns_none_for_no_human_messages(self):
            """Test returning None when no HumanMessages exist."""
            state = {"messages": [AIMessage(content="Only AI")]}
            result = MessageExtractor.extract_last_human_message(state)
            assert result is None

        def test_returns_none_for_empty_messages(self):
            """Test returning None for empty messages list."""
            state = {"messages": []}
            result = MessageExtractor.extract_last_human_message(state)
            assert result is None

        def test_returns_none_for_missing_messages_key(self):
            """Test returning None when messages key is missing."""
            state = {}
            result = MessageExtractor.extract_last_human_message(state)
            assert result is None

        def test_strips_whitespace(self):
            """Test that result is stripped of whitespace."""
            state = {"messages": [HumanMessage(content="  Hello  ")]}
            result = MessageExtractor.extract_last_human_message(state)
            assert result == "Hello"

    class TestExtractLastMessageContent:
        """Tests for extract_last_message_content method."""

        def test_extracts_from_human_message(self):
            """Test extracting from HumanMessage."""
            state = {"messages": [HumanMessage(content="User message")]}
            result = MessageExtractor.extract_last_message_content(state)
            assert result == "User message"

        def test_extracts_from_ai_message(self):
            """Test extracting from AIMessage."""
            state = {"messages": [AIMessage(content="AI response")]}
            result = MessageExtractor.extract_last_message_content(state)
            assert result == "AI response"

        def test_extracts_from_dict_message(self):
            """Test extracting from dict message."""
            state = {"messages": [{"content": "Dict message"}]}
            result = MessageExtractor.extract_last_message_content(state)
            assert result == "Dict message"

        def test_returns_none_for_empty(self):
            """Test returning None for empty state."""
            assert MessageExtractor.extract_last_message_content({}) is None
            assert MessageExtractor.extract_last_message_content({"messages": []}) is None

    class TestExtractMessageContent:
        """Tests for extract_message_content method."""

        def test_extracts_from_object_with_content(self):
            """Test extracting from object with content attribute."""
            message = HumanMessage(content="Test content")
            result = MessageExtractor.extract_message_content(message)
            assert result == "Test content"

        def test_extracts_from_dict(self):
            """Test extracting from dict."""
            message = {"content": "Dict content", "role": "user"}
            result = MessageExtractor.extract_message_content(message)
            assert result == "Dict content"

        def test_converts_other_to_string(self):
            """Test converting other types to string."""
            result = MessageExtractor.extract_message_content("plain string")
            assert result == "plain string"

    class TestHasMessages:
        """Tests for has_messages method."""

        def test_returns_true_for_non_empty(self):
            """Test returning True for non-empty messages."""
            state = {"messages": [HumanMessage(content="Hello")]}
            assert MessageExtractor.has_messages(state) is True

        def test_returns_false_for_empty(self):
            """Test returning False for empty messages."""
            assert MessageExtractor.has_messages({}) is False
            assert MessageExtractor.has_messages({"messages": []}) is False
