"""Tests for groq_search module — Groq browser search functionality."""

import unittest
from unittest.mock import MagicMock, patch

from web_search_mcp.groq_search import browse
from web_search_mcp.models import ErrorResponse


class TestGroqBrowse:
    """Unit tests for groq browse function."""

    @patch("web_search_mcp.groq_search.settings")
    def test_empty_query_returns_error(self, mock_settings):
        result = browse("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.settings")
    def test_whitespace_query_returns_error(self, mock_settings):
        result = browse("   ")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = browse("test query")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_successful_search(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "Search results about AI trends in 2025..."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        result = browse("AI trends 2025")

        assert isinstance(result, str)
        assert "AI trends" in result
        mock_groq_cls.assert_called_once_with(api_key="gsk_test123")
        mock_client.chat.completions.create.assert_called_once()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_groq_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_groq_cls.return_value = mock_client

        result = browse("test query")
        assert isinstance(result, ErrorResponse)
        assert "rate limit" in result.details.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_empty_content_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        result = browse("test query")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_reasoning_effort_passed_to_groq(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "result"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        browse("test query", reasoning_effort="high")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_model_param_forwarded(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "result"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        browse("test query", model="openai/gpt-oss-120b")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-oss-120b"

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_default_model_is_oss20b(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "result"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        browse("test query")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-oss-20b"

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_browser_search_tool_type_in_calls(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "result"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        browse("test query")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["tools"] == [{"type": "browser_search"}]


if __name__ == "__main__":
    unittest.main()
