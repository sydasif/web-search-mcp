"""Tests for groq_tools module — Groq Compound system tools."""

from unittest.mock import MagicMock, patch

from web_search_mcp.groq_tools import (
    search,
    analyze_page,
)
from web_search_mcp.groq_client import truncate_query
from web_search_mcp.models import ErrorResponse


class TestTruncateQuery:
    """Unit tests for truncate_query helper."""

    def test_short_query_unchanged(self):
        result = truncate_query("What is Python?")
        assert result == "What is Python?"

    def test_whitespace_normalized(self):
        result = truncate_query("  What   is   Python?  ")
        assert result == "What is Python?"

    def test_long_query_truncated(self):
        long_query = "x " * 5000  # ~10000 bytes
        result = truncate_query(long_query, max_bytes=3000)
        assert len(result.encode("utf-8")) <= 3000

    def test_unicode_query_truncated(self):
        # Non-ASCII chars expand in UTF-8 — é = 2 bytes
        query = "é" * 2000  # ~4000 bytes UTF-8
        result = truncate_query(query, max_bytes=3000)
        assert len(result.encode("utf-8")) <= 3000

    def test_no_mid_character_split(self):
        query = "ä" * 1000  # ä = 2 bytes UTF-8
        result = truncate_query(query, max_bytes=3001)
        assert len(result.encode("utf-8")) <= 3001


class TestSearch:
    """Unit tests for search function (merged browse + research)."""

    @patch("web_search_mcp.groq_client.settings")
    def test_empty_query_returns_error(self, mock_settings):
        result = search("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = search("test")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_successful_compound_search(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "Research results with citations..."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        result = search("Latest AI developments")

        assert isinstance(result, str)
        assert "Research results" in result
        mock_groq_cls.assert_called_once_with(
            api_key="gsk_test123",
            default_headers={"Groq-Model-Version": "latest"},
        )

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

        search("test")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "groq/compound-mini"

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_compound_full_model(self, mock_settings, mock_groq_cls):
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

        search("test", model="groq/compound")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "groq/compound"

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_groq_cls.return_value = mock_client

        result = search("test")
        assert isinstance(result, ErrorResponse)

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

        result = search("test")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_413_error_returns_helpful_message(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Error code: 413 - {'error': {'message': 'Request Entity Too Large'}}"
        )
        mock_groq_cls.return_value = mock_client

        result = search("test")
        assert isinstance(result, ErrorResponse)
        assert "too large" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_long_query_truncated(self, mock_settings, mock_groq_cls):
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

        long_query = (
            "What is the latest version of Python and what new features does it introduce? " * 100
        )
        search(long_query)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        sent_query = call_kwargs["messages"][0]["content"]
        assert len(sent_query.encode("utf-8")) <= 3000


class TestAnalyzePage:
    """Unit tests for analyze_page function."""

    @patch("web_search_mcp.groq_client.settings")
    def test_empty_url_returns_error(self, mock_settings):
        result = analyze_page("")
        assert isinstance(result, ErrorResponse)
        assert "url cannot be empty" in result.error.lower()

    @patch("web_search_mcp.groq_client.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_successful_visit(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "The page discusses AI trends..."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        result = analyze_page("https://example.com")

        assert isinstance(result, str)
        assert "AI trends" in result

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_custom_query_forwarded(self, mock_settings, mock_groq_cls):
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

        analyze_page("https://example.com", query="Extract the table of contents")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        msg = call_kwargs["messages"][0]["content"]
        assert "Extract the table of contents" in msg
        assert "example.com" in msg

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit")
        mock_groq_cls.return_value = mock_client

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_413_error_returns_helpful_message(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Error code: 413 - {'error': {'message': 'Request Entity Too Large'}}"
        )
        mock_groq_cls.return_value = mock_client

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "too large" in result.error.lower()

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

        analyze_page("https://example.com")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "groq/compound-mini"
