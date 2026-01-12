"""Tests for MessageExtractor utility."""

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
