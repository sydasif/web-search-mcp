"""Tests for groq_tools module — Groq search functionality (merged browse + compound)."""

import unittest
from unittest.mock import MagicMock, patch

from web_search_mcp.groq_tools import search
from web_search_mcp.models import ErrorResponse


class TestGroqSearch:
    """Unit tests for groq search function."""

    @patch("web_search_mcp.groq_client.settings")
    def test_empty_query_returns_error(self, mock_settings):
        result = search("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.settings")
    def test_whitespace_query_returns_error(self, mock_settings):
        result = search("   ")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = search("test query")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
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

        result = search("AI trends 2025")

        assert isinstance(result, str)
        assert "AI trends" in result
        mock_groq_cls.assert_called_once_with(
            api_key="gsk_test123", default_headers={"Groq-Model-Version": "latest"}
        )
        mock_client.chat.completions.create.assert_called_once()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_groq_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_groq_cls.return_value = mock_client

        result = search("test query")
        assert isinstance(result, ErrorResponse)
        assert "rate limit" in result.details.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
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

        result = search("test query")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_reasoning_effort_passed_to_gpt_oss(self, mock_settings, mock_groq_cls):
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

        search("test query", model="openai/gpt-oss-20b", reasoning_effort="high")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"
        assert call_kwargs["model"] == "openai/gpt-oss-20b"

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_browser_search_tool_used_for_gpt_oss(self, mock_settings, mock_groq_cls):
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

        search("test query", model="openai/gpt-oss-20b")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["tools"] == [{"type": "browser_search"}]

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_compound_model_no_browser_tools(self, mock_settings, mock_groq_cls):
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

        search("test query", model="groq/compound-mini")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # Compound models should NOT use browser_search tool
        assert call_kwargs.get("tools") is None

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_default_model_is_compound_mini(self, mock_settings, mock_groq_cls):
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

        search("test query")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "groq/compound-mini"


if __name__ == "__main__":
    unittest.main()
