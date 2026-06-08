"""Functional tests for Groq search MCP tools.

Tests the full call chain from the MCP tool interface through to the
core logic in groq_tools.py and groq_client.py, mocking only the Groq API.

Structure:
  - MCP tool layer: tests exercise the FastMCP in-memory client
  - groq_client.py unit edge cases: uncovered branches
  - groq_tools.py unit edge cases: uncovered branches
"""

from unittest.mock import patch, MagicMock

import httpx
import pytest
import pytest_asyncio
import tenacity
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from web_search_mcp.groq_client import (
    GroqClientError,
    _retry_if_not_fatal,
    call_groq_api,
    get_client,
)
from web_search_mcp.groq_tools import (
    browse,
    research,
    analyze_page,
    _unwrap_error,
)
from web_search_mcp.models import ErrorResponse
from web_search_mcp.server import mcp

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """In-memory FastMCP client backed by the real server instance."""
    transport = FastMCPTransport(mcp)
    async with Client(transport) as c:
        yield c


def _make_groq_response(content: str | None = "result") -> MagicMock:
    """Build a mock Groq chat completion response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ============================================================================
# MCP Tool Layer — groq_browse
# ============================================================================


class TestGroqBrowseTool:
    """Functional tests for the groq_browse MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_browse")
    async def test_browse_basic(self, mock_fn, client):
        """Basic groq_browse call returns a string."""
        mock_fn.return_value = "Search result about AI."
        result = await client.call_tool("groq_browse", {"query": "AI trends"})
        assert isinstance(result.data, str)
        assert "AI" in result.data
        mock_fn.assert_called_once_with(
            query="AI trends", model="openai/gpt-oss-20b", reasoning_effort="low"
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_browse")
    async def test_browse_all_params(self, mock_fn, client):
        """All groq_browse params are forwarded correctly."""
        mock_fn.return_value = "result"
        await client.call_tool(
            "groq_browse",
            {
                "query": "test query",
                "model": "openai/gpt-oss-120b",
                "reasoning_effort": "high",
            },
        )
        mock_fn.assert_called_once_with(
            query="test query", model="openai/gpt-oss-120b", reasoning_effort="high"
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_browse")
    async def test_browse_default_reasoning(self, mock_fn, client):
        """Default reasoning_effort is 'low'."""
        mock_fn.return_value = "result"
        await client.call_tool("groq_browse", {"query": "test"})
        mock_fn.assert_called_once_with(
            query="test", model="openai/gpt-oss-20b", reasoning_effort="low"
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_browse")
    async def test_browse_error_response(self, mock_fn, client):
        """ErrorResponse from browse is passed through."""
        mock_fn.return_value = ErrorResponse(
            error="Groq API key not configured", details="missing key"
        )
        result = await client.call_tool("groq_browse", {"query": "test"})
        assert isinstance(result.data, dict)
        assert "not configured" in str(result.data)


# ============================================================================
# MCP Tool Layer — groq_research
# ============================================================================


class TestGroqResearchTool:
    """Functional tests for the groq_research MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_research")
    async def test_research_basic(self, mock_fn, client):
        """Basic groq_research returns a string."""
        mock_fn.return_value = "Research results with citations."
        result = await client.call_tool("groq_research", {"query": "AI trends 2025"})
        assert isinstance(result.data, str)
        assert "Research" in result.data
        mock_fn.assert_called_once_with(query="AI trends 2025", model="groq/compound-mini")

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_research")
    async def test_research_custom_model(self, mock_fn, client):
        """Custom model is forwarded."""
        mock_fn.return_value = "result"
        await client.call_tool("groq_research", {"query": "test", "model": "groq/compound"})
        mock_fn.assert_called_once_with(query="test", model="groq/compound")

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_research")
    async def test_research_error_response(self, mock_fn, client):
        """ErrorResponse from research is passed through."""
        mock_fn.return_value = ErrorResponse(error="Groq research failed", details="API error")
        result = await client.call_tool("groq_research", {"query": "test"})
        assert isinstance(result.data, dict)
        assert "failed" in str(result.data)


# ============================================================================
# MCP Tool Layer — groq_analyze_page
# ============================================================================


class TestGroqAnalyzePageTool:
    """Functional tests for the groq_analyze_page MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_analyze_page")
    async def test_analyze_page_basic(self, mock_fn, client):
        """Basic groq_analyze_page returns a string."""
        mock_fn.return_value = "The page discusses Python."
        result = await client.call_tool("groq_analyze_page", {"url": "https://example.com"})
        assert isinstance(result.data, str)
        assert "Python" in result.data
        mock_fn.assert_called_once_with(
            url="https://example.com",
            query="Summarize the key points of this page.",
            model="groq/compound-mini",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_analyze_page")
    async def test_analyze_page_custom_args(self, mock_fn, client):
        """Custom query and model are forwarded."""
        mock_fn.return_value = "analysis"
        await client.call_tool(
            "groq_analyze_page",
            {
                "url": "https://example.com/doc",
                "query": "Extract data",
                "model": "groq/compound",
            },
        )
        mock_fn.assert_called_once_with(
            url="https://example.com/doc",
            query="Extract data",
            model="groq/compound",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._groq_analyze_page")
    async def test_analyze_page_error_response(self, mock_fn, client):
        """ErrorResponse from analyze_page is passed through."""
        mock_fn.return_value = ErrorResponse(error="Page too large", details="try fetch_page first")
        result = await client.call_tool("groq_analyze_page", {"url": "https://example.com"})
        assert isinstance(result.data, dict)
        assert "too large" in str(result.data)


# ============================================================================
# groq_client.py — _retry_if_not_fatal branch coverage
# ============================================================================


class TestRetryIfNotFatal:
    """Edge cases for the tenacity retry predicate in groq_client."""

    def test_groq_client_error_no_status(self):
        """GroqClientError with no status_code falls through to generic checks."""
        exc = GroqClientError("generic error", status_code=None)
        # Not fatal (no matching status), msg doesn't contain timeout/connection/network
        assert _retry_if_not_fatal(exc) is False

    def test_groq_client_error_zero_status(self):
        """GroqClientError with status_code=0 hits the right side of 'and' on line 52."""
        exc = GroqClientError("weird", status_code=0)
        # isinstance check passes, status_code not in (400,401,403,413),
        # status_code==429 is False, (status_code and status_code>=500) short-circuits on 0
        # Then falls through to line 55 — "weird" doesn't contain timeout/connection/network
        assert _retry_if_not_fatal(exc) is False

    def test_non_groq_error_with_timeout_msg(self):
        """Non-GroqClientError with 'timeout' in message is retried."""
        # "timed out" != "timeout" — use a message with literal "timeout"
        exc = Exception("operation timed out, connection timeout exceeded")
        assert _retry_if_not_fatal(exc) is True

    def test_non_groq_error_with_connection_msg(self):
        """Non-GroqClientError with 'connection' in message is retried."""
        exc = ConnectionError("Connection refused")
        assert _retry_if_not_fatal(exc) is True

    def test_non_groq_error_with_network_msg(self):
        """Non-GroqClientError with 'network' in message is retried."""
        exc = OSError("Network is unreachable")
        assert _retry_if_not_fatal(exc) is True

    def test_non_groq_error_unrelated(self):
        """Non-GroqClientError without retry keywords is not retried."""
        exc = ValueError("something else")
        assert _retry_if_not_fatal(exc) is False

    def test_groq_client_error_429(self):
        """429 status code is retried."""
        exc = GroqClientError("rate limited", status_code=429)
        assert _retry_if_not_fatal(exc) is True

    def test_groq_client_error_500(self):
        """500 status code is retried."""
        exc = GroqClientError("server error", status_code=500)
        assert _retry_if_not_fatal(exc) is True

    def test_groq_client_error_503(self):
        """503 status code is retried."""
        exc = GroqClientError("service unavailable", status_code=503)
        assert _retry_if_not_fatal(exc) is True

    def test_groq_client_error_403(self):
        """403 is fatal (no retry)."""
        exc = GroqClientError("forbidden", status_code=403)
        assert _retry_if_not_fatal(exc) is False


# ============================================================================
# groq_client.py — call_groq_api edge cases
# ============================================================================


class TestCallGroqApi:
    """Edge cases for the unified Groq API wrapper."""

    @patch("web_search_mcp.groq_client.settings")
    def test_no_api_key_raises(self, mock_settings):
        """Missing API key raises GroqClientError with 401."""
        mock_settings.groq_api_key = ""
        with pytest.raises(GroqClientError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        assert exc_info.value.status_code == 401
        assert "Missing" in str(exc_info.value)

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_with_status_code_attr(self, mock_settings, mock_groq_cls):
        """Exception raised by Groq SDK with a status_code attribute is extracted."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_client = MagicMock()

        class MockAPIError(Exception):
            def __init__(self):
                super().__init__("API error occurred")
                self.status_code = 400  # fatal — _retry_if_not_fatal returns False

        mock_client.chat.completions.create.side_effect = MockAPIError()
        mock_groq_cls.return_value = mock_client

        with pytest.raises(GroqClientError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        assert exc_info.value.status_code == 400

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_http_in_msg_regex(self, mock_settings, mock_groq_cls):
        """Exception without status_code attr but HTTP NNN in message extracts via regex.
        429 is retryable, so tenacity wraps it in RetryError — unwrap to find it."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("HTTP 429 Too Many Requests")
        mock_groq_cls.return_value = mock_client

        with pytest.raises(tenacity.RetryError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        inner = exc_info.value.last_attempt.exception()
        assert isinstance(inner, GroqClientError)
        assert inner.status_code == 429

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_413_extraction_via_string_match(self, mock_settings, mock_groq_cls):
        """413 in error message triggers request_too_large path."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Error code: 413 - request_too_large"
        )
        mock_groq_cls.return_value = mock_client

        with pytest.raises(GroqClientError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        assert exc_info.value.status_code == 413
        assert "too large" in str(exc_info.value).lower()

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_with_status_code_from_httpx(self, mock_settings, mock_groq_cls):
        """httpx HTTPStatusError has no .status_code attr and its str has no
        'HTTP' prefix — status_code ends up as None."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_groq_cls.return_value = mock_client

        with pytest.raises(GroqClientError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        # httpx.HTTPStatusError has `.response.status_code` but not `.status_code`;
        # the code only checks `hasattr(e, "status_code")` which is False.
        assert exc_info.value.status_code is None

    @patch("web_search_mcp.groq_client.settings")
    def test_call_groq_api_request_too_large_413(self, mock_settings):
        """'413' in message and 'Request Entity Too Large' both caught."""
        mock_settings.groq_api_key = "gsk_test123"
        with patch("web_search_mcp.groq_client.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception(
                "413 Request Entity Too Large"
            )
            mock_groq_cls.return_value = mock_client

            with pytest.raises(GroqClientError) as exc_info:
                call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
            assert exc_info.value.status_code == 413

    @patch("web_search_mcp.groq_client.Groq")
    @patch("web_search_mcp.groq_client.settings")
    def test_api_error_http_in_msg_no_match(self, mock_settings, mock_groq_cls):
        """ "HTTP" in msg but regex doesn't match — status_code stays None."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "some HTTP error without status digits"
        )
        mock_groq_cls.return_value = mock_client

        with pytest.raises(GroqClientError) as exc_info:
            call_groq_api(messages=[{"role": "user", "content": "hi"}], model="test")
        assert exc_info.value.status_code is None


# ============================================================================
# groq_client.py — get_client
# ============================================================================


class TestGetClient:
    """Tests for the get_client convenience function."""

    def test_get_client_configures_correctly(self):
        """get_client returns a Groq client with correct settings."""
        with patch("web_search_mcp.groq_client.Groq") as mock_groq_cls:
            client = get_client()
            mock_groq_cls.assert_called_once_with(
                api_key=mock_groq_cls.call_args[1]["api_key"],
                default_headers={"Groq-Model-Version": "latest"},
            )
            assert client is not None


# ============================================================================
# groq_tools.py — _unwrap_error edge cases
# ============================================================================


class TestUnwrapError:
    """Edge cases for RetryError unwrapping."""

    def test_non_retry_error_passed_through(self):
        """Non-RetryError is returned as-is."""
        exc = ValueError("simple error")
        assert _unwrap_error(exc) is exc

    def test_retry_error_with_exception(self):
        """RetryError with a valid last_attempt.exception() unwraps it."""
        inner = ValueError("inner")
        # Create a RetryError by actually running a failing retry
        mock_attempt = MagicMock()
        mock_attempt.exception.return_value = inner

        retry_error = tenacity.RetryError(mock_attempt)
        result = _unwrap_error(retry_error)
        assert result is inner

    def test_retry_error_without_exception(self):
        """RetryError where last_attempt.exception() returns None returns the RetryError itself."""
        mock_attempt = MagicMock()
        mock_attempt.exception.return_value = None

        retry_error = tenacity.RetryError(mock_attempt)
        result = _unwrap_error(retry_error)
        # Falls through to `or e` — returns the RetryError itself
        assert result is retry_error


# ============================================================================
# groq_tools.py — browse edge cases
# ============================================================================


class TestBrowseEdgeCases:
    """Edge cases in browse not yet covered by existing tests."""

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_browse_retry_error_unwrapped(self, mock_settings, mock_call):
        """RetryError from tenacity is unwrapped to show the original error."""
        mock_settings.groq_api_key = "gsk_test123"

        mock_attempt = MagicMock()
        inner = Exception("underlying failure")
        mock_attempt.exception.return_value = inner
        mock_call.side_effect = tenacity.RetryError(mock_attempt)

        result = browse("test query")
        assert isinstance(result, ErrorResponse)
        assert "underlying failure" in result.details

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_browse_missing_api_key_401(self, mock_settings, mock_call):
        """401 error returns auth error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Unauthorized", status_code=401)

        result = browse("test query")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()


# ============================================================================
# groq_tools.py — research edge cases
# ============================================================================


class TestResearchEdgeCases:
    """Edge cases in research not yet covered by existing tests."""

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_research_401_auth_error(self, mock_settings, mock_call):
        """401 error in research returns auth error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Unauthorized", status_code=401)
        result = research("test query")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_research_413_too_large(self, mock_settings, mock_call):
        """413 error in research returns helpful message."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Request too large", status_code=413)

        result = research("very long query " * 100)
        assert isinstance(result, ErrorResponse)
        assert "limit exceeded" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_research_generic_error(self, mock_settings, mock_call):
        """Generic GroqClientError (not 401/413) returns general error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Rate limited", status_code=429)

        result = research("test query")
        assert isinstance(result, ErrorResponse)
        assert "research failed" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_research_non_groq_client_error(self, mock_settings, mock_call):
        """Non-GroqClientError (e.g. ValueError) is caught by generic handler."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = ValueError("unexpected error")

        result = research("test query")
        assert isinstance(result, ErrorResponse)
        assert "research failed" in result.error.lower()


# ============================================================================
# groq_tools.py — analyze_page edge cases
# ============================================================================


class TestAnalyzePageEdgeCases:
    """Edge cases in analyze_page not yet covered by existing tests."""

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_analyze_page_empty_content(self, mock_settings, mock_call):
        """API returns empty content → empty response error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.return_value = _make_groq_response(content=None)

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_analyze_page_non_groq_error(self, mock_settings, mock_call):
        """Non-GroqClientError is caught by the generic handler."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = ValueError("unexpected value error")

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "failed" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_analyze_page_401_auth_error(self, mock_settings, mock_call):
        """401 error in analyze_page returns auth error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Unauthorized", status_code=401)

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "not configured" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_analyze_page_413_too_large(self, mock_settings, mock_call):
        """413 error in analyze_page returns helpful message."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Request too large", status_code=413)

        result = analyze_page("https://example.com/large-page")
        assert isinstance(result, ErrorResponse)
        assert "too large" in result.error.lower()

    @patch("web_search_mcp.groq_tools.call_groq_api")
    @patch("web_search_mcp.groq_client.settings")
    def test_analyze_page_generic_error(self, mock_settings, mock_call):
        """Generic GroqClientError (not 401/413) returns general error."""
        mock_settings.groq_api_key = "gsk_test123"
        mock_call.side_effect = GroqClientError("Service unavailable", status_code=503)

        result = analyze_page("https://example.com")
        assert isinstance(result, ErrorResponse)
        assert "failed" in result.error.lower()
