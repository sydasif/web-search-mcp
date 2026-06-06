"""Tests for groq_search module — Groq browser search functionality."""

import unittest
from unittest.mock import MagicMock, patch

from web_search_mcp.groq_search import browser_search
from web_search_mcp.models import ErrorResponse


class TestBrowserSearch:
    """Unit tests for browser_search function."""

    @patch("web_search_mcp.groq_search.settings")
    def test_empty_query_returns_error(self, mock_settings):
        """Empty query returns ErrorResponse."""
        result = browser_search("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.settings")
    def test_whitespace_query_returns_error(self, mock_settings):
        """Whitespace-only query returns ErrorResponse."""
        result = browser_search("   ")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        """Missing GROQ_API_KEY returns ErrorResponse."""
        mock_settings.groq_api_key = ""
        result = browser_search("test query")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_successful_search(self, mock_settings, mock_groq_cls):
        """Successful search returns content string."""
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

        result = browser_search("AI trends 2025")

        assert isinstance(result, str)
        assert "AI trends" in result
        mock_groq_cls.assert_called_once_with(api_key="gsk_test123")
        mock_client.chat.completions.create.assert_called_once()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_groq_api_error_returns_error(self, mock_settings, mock_groq_cls):
        """Groq API failure returns ErrorResponse."""
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_groq_cls.return_value = mock_client

        result = browser_search("test query")
        assert isinstance(result, ErrorResponse)
        assert "rate limit" in result.details.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_empty_content_returns_error(self, mock_settings, mock_groq_cls):
        """Empty model content returns ErrorResponse."""
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

        result = browser_search("test query")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_reasoning_effort_passed_to_groq(self, mock_settings, mock_groq_cls):
        """reasoning_effort param is forwarded to Groq API."""
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

        browser_search("test query", reasoning_effort="high")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"

    @patch("web_search_mcp.groq_search.Groq")
    @patch("web_search_mcp.groq_search.settings")
    def test_browser_search_tool_type_in_calls(self, mock_settings, mock_groq_cls):
        """Tool type is set to browser_search."""
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

        browser_search("test query")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["tools"] == [{"type": "browser_search"}]
        assert call_kwargs["tool_choice"] == "required"


if __name__ == "__main__":
    unittest.main()
