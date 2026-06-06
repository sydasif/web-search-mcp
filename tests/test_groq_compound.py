"""Tests for groq_compound module — Groq Compound system tools."""

from unittest.mock import MagicMock, patch

from web_search_mcp.groq_compound import compound_search, visit_website
from web_search_mcp.models import ErrorResponse


class TestCompoundSearch:
    """Unit tests for compound_search function."""

    @patch("web_search_mcp.groq_compound.settings")
    def test_empty_query_returns_error(self, mock_settings):
        result = compound_search("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_compound.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = compound_search("test")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
    def test_successful_search(self, mock_settings, mock_groq_cls):
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

        result = compound_search("Latest AI developments")

        assert isinstance(result, str)
        assert "Research results" in result
        mock_groq_cls.assert_called_once_with(
            api_key="gsk_test123",
            default_headers={"Groq-Model-Version": "latest"},
        )

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
    def test_compound_mini_model(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_message = MagicMock()
        mock_message.content = "quick result"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_client

        compound_search("test", model="groq/compound-mini")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "groq/compound-mini"

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
    def test_enabled_tools_in_call(self, mock_settings, mock_groq_cls):
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

        compound_search("test")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["compound_custom"]["tools"]["enabled_tools"] == ["web_search"]

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
    def test_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_groq_cls.return_value = mock_client

        result = compound_search("test")
        assert isinstance(result, ErrorResponse)

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
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

        result = compound_search("test")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()


class TestVisitWebsite:
    """Unit tests for visit_website function."""

    @patch("web_search_mcp.groq_compound.settings")
    def test_empty_url_returns_error(self, mock_settings):
        result = visit_website("")
        assert isinstance(result, ErrorResponse)
        assert "url cannot be empty" in result.error.lower()

    @patch("web_search_mcp.groq_compound.settings")
    def test_missing_api_key_returns_error(self, mock_settings):
        mock_settings.groq_api_key = ""
        result = visit_website("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
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

        result = visit_website("https://example.com")

        assert isinstance(result, str)
        assert "AI trends" in result

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
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

        visit_website("https://example.com", query="Extract the table of contents")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        msg = call_kwargs["messages"][0]["content"]
        assert "Extract the table of contents" in msg
        assert "example.com" in msg

    @patch("web_search_mcp.groq_compound.Groq")
    @patch("web_search_mcp.groq_compound.settings")
    def test_api_error_returns_error(self, mock_settings, mock_groq_cls):
        mock_settings.groq_api_key = "gsk_test123"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit")
        mock_groq_cls.return_value = mock_client

        result = visit_website("https://example.com")
        assert isinstance(result, ErrorResponse)
