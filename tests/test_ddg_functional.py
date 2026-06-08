"""Functional tests for DDG search MCP tools.

Tests the full call chain from the MCP tool interface through to the
core logic in ddg.py, mocking only external network services (DDGS,
httpx, curl_cffi, trafilatura).

Structure:
  - MCP tool layer: tests exercise the FastMCP in-memory client
  - ddg.py unit edge cases: missing branch coverage in core functions
"""

from unittest.mock import patch, MagicMock

import httpx
import pytest
import pytest_asyncio
import tenacity
from curl_cffi import CurlError
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from web_search_mcp.ddg import (
    _should_retry_ddg,
    _request_with_fallback,
    _fetch_httpx,
    _fetch_curl,
    fetch_page,
)
from web_search_mcp.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    PageResponse,
    ErrorResponse,
)
from web_search_mcp.server import mcp

# ── Helpers ────────────────────────────────────────────────────────────────


def make_search_response(
    query: str = "test",
    results: list[SearchResult] | None = None,
    has_more: bool = False,
) -> SearchResponse:
    return SearchResponse(
        query=query,
        search_type="text",
        total_results=len(results) if results else 0,
        results=results or [],
        has_more=has_more,
        next_page=2 if has_more else None,
    )


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """In-memory FastMCP client backed by the real server instance."""
    transport = FastMCPTransport(mcp)
    async with Client(transport) as c:
        yield c


# ============================================================================
# MCP Tool Layer — web_search
# ============================================================================


class TestWebSearchTool:
    """Functional tests for the web_search MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_returns_markdown_by_default(self, mock_ddg, client):
        """Default response_format='markdown' returns a formatted string."""
        mock_ddg.return_value = make_search_response(
            results=[SearchResult(title="Result A", href="https://a.com", body="Body A")],
        )
        result = await client.call_tool("web_search", {"query": "hello", "max_results": 5})
        assert "**[Result A](https://a.com)**" in result.data
        assert "Body A" in result.data

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_json_format(self, mock_ddg, client):
        """response_format='json' returns a SearchResponse dict."""
        mock_ddg.return_value = make_search_response(
            results=[SearchResult(title="Json Result", href="https://j.com")],
        )
        result = await client.call_tool(
            "web_search",
            {"query": "hello", "response_format": "json", "max_results": 5},
        )
        assert isinstance(result.data, dict)
        assert "results" in result.data

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_error_response_markdown(self, mock_ddg, client):
        """When ddg_search returns ErrorResponse with markdown, format it."""
        mock_ddg.return_value = ErrorResponse(error="API limit", details="retry later")
        result = await client.call_tool("web_search", {"query": "hello"})
        assert "**Error:** API limit" in result.data

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_error_response_json(self, mock_ddg, client):
        """When ddg_search returns ErrorResponse with json, return it as-is."""
        mock_ddg.return_value = ErrorResponse(error="API limit", details="retry later")
        result = await client.call_tool("web_search", {"query": "hello", "response_format": "json"})
        assert isinstance(result.data, dict)
        assert result.data["error"] == "API limit"

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_unexpected_exception(self, mock_ddg, client):
        """Unexpected exceptions are caught by the server wrapper."""
        mock_ddg.side_effect = RuntimeError("unexpected failure")
        result = await client.call_tool("web_search", {"query": "hello"})
        assert isinstance(result.data, dict)
        assert "error" in result.data
        assert "unexpected failure" in str(result.data)

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_forwards_request_params(self, mock_ddg, client):
        """All search parameters are forwarded to ddg_search correctly."""
        mock_ddg.return_value = make_search_response()
        await client.call_tool(
            "web_search",
            {
                "query": "test query",
                "search_type": "news",
                "max_results": 10,
                "time_range": "w",
                "region": "us-en",
                "safesearch": "off",
                "page": 2,
                "backend": "api",
                "response_format": "json",
            },
        )
        mock_ddg.assert_called_once()
        req: SearchRequest = mock_ddg.call_args[0][0]
        assert req.query == "test query"
        assert req.search_type == "news"
        assert req.max_results == 10
        assert req.time_range == "w"
        assert req.region == "us-en"
        assert req.safesearch == "off"
        assert req.page == 2
        assert req.backend == "api"
        assert req.response_format == "json"

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_pagination_marker(self, mock_ddg, client):
        """Pagination indicator appears in markdown when has_more is True."""
        mock_ddg.return_value = make_search_response(
            results=[SearchResult(title="P", href="https://p.com", body="B")],
            has_more=True,
        )
        result = await client.call_tool(
            "web_search", {"query": "page-me", "response_format": "markdown"}
        )
        assert "More results available" in result.data

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_web_search_empty_results(self, mock_ddg, client):
        """Empty search results still produce valid markdown."""
        mock_ddg.return_value = make_search_response()
        result = await client.call_tool(
            "web_search", {"query": "nothing", "response_format": "markdown"}
        )
        assert "No results found" in result.data
        assert "Found 0 results" in result.data


# ============================================================================
# MCP Tool Layer — fetch_page
# ============================================================================


class TestFetchPageTool:
    """Functional tests for the fetch_page MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._fetch_page")
    async def test_fetch_page_basic(self, mock_fn, client):
        """Basic fetch_page call returns PageResponse."""
        mock_fn.return_value = PageResponse(url="https://example.com", length=4, content="text")
        result = await client.call_tool("fetch_page", {"url": "https://example.com"})
        mock_fn.assert_called_once_with(
            url="https://example.com",
            output_format="txt",
            include_metadata=False,
            include_tables=False,
            include_comments=False,
            include_images=False,
            deduplicate=True,
            max_length=15000,
            timeout=30,
            backend="auto",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._fetch_page")
    async def test_fetch_page_parameters(self, mock_fn, client):
        """Fetch_page passes all custom parameters correctly."""
        mock_fn.return_value = PageResponse(url="https://example.com", length=4, content="data")
        await client.call_tool(
            "fetch_page",
            {
                "url": "https://example.com",
                "output_format": "markdown",
                "include_metadata": True,
                "include_tables": True,
                "include_comments": True,
                "include_images": True,
                "deduplicate": False,
                "max_length": 500,
                "timeout": 15,
                "backend": "curl",
            },
        )
        mock_fn.assert_called_once_with(
            url="https://example.com",
            output_format="markdown",
            include_metadata=True,
            include_tables=True,
            include_comments=True,
            include_images=True,
            deduplicate=False,
            max_length=500,
            timeout=15,
            backend="curl",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._fetch_page")
    async def test_fetch_page_error_response(self, mock_fn, client):
        """ErrorResponse from fetch_page is passed through."""
        mock_fn.return_value = ErrorResponse(error="Could not download content.", details="Timeout")
        result = await client.call_tool("fetch_page", {"url": "https://example.com/empty"})
        assert isinstance(result.data, dict)
        assert result.data["error"] == "Could not download content."


# ============================================================================
# MCP Tool Layer — search_docs
# ============================================================================


class TestSearchDocsTool:
    """Functional tests for the search_docs MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_search_docs_basic(self, mock_ddg, client):
        """search_docs constructs site: query and calls ddg_search."""
        mock_ddg.return_value = make_search_response(
            results=[SearchResult(title="Doc", href="https://d.com", body="Info")],
        )
        await client.call_tool("search_docs", {"query": "asyncio", "domain": "docs.python.org"})
        mock_ddg.assert_called_once()
        req: SearchRequest = mock_ddg.call_args[0][0]
        assert req.query == "site:docs.python.org asyncio"
        assert req.max_results == 5

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_search_docs_default_domain(self, mock_ddg, client):
        """search_docs defaults to docs.python.org."""
        mock_ddg.return_value = make_search_response()
        await client.call_tool("search_docs", {"query": "os.path"})
        req: SearchRequest = mock_ddg.call_args[0][0]
        assert req.query == "site:docs.python.org os.path"

    @pytest.mark.asyncio
    @patch("web_search_mcp.server.ddg_search")
    async def test_search_docs_unexpected_exception(self, mock_ddg, client):
        """Unexpected exceptions in search_docs are caught."""
        mock_ddg.side_effect = RuntimeError("search_docs boom")
        result = await client.call_tool("search_docs", {"query": "testing"})
        assert isinstance(result.data, dict)
        assert "search_docs boom" in str(result.data)


# ============================================================================
# ddg.py — _should_retry_ddg branch coverage
# ============================================================================


class TestShouldRetryDDG:
    """Edge cases for the tenacity retry predicate."""

    @pytest.mark.parametrize(
        ("exception", "expected"),
        [
            # 429 rate limit → retry
            (
                httpx.HTTPStatusError(
                    "429", request=MagicMock(), response=MagicMock(status_code=429)
                ),
                True,
            ),
            # 5xx server errors → retry
            (
                httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=MagicMock(status_code=500)
                ),
                True,
            ),
            (
                httpx.HTTPStatusError(
                    "502", request=MagicMock(), response=MagicMock(status_code=502)
                ),
                True,
            ),
            # 4xx other → no retry
            (
                httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=MagicMock(status_code=404)
                ),
                False,
            ),
            (
                httpx.HTTPStatusError(
                    "403", request=MagicMock(), response=MagicMock(status_code=403)
                ),
                False,
            ),
            # Transport-level → retry
            (httpx.TimeoutException("timeout"), True),
            (httpx.RequestError("connection failed"), True),
            # Other → no retry
            (ValueError("nope"), False),
            (RuntimeError("boom"), False),
        ],
    )
    def test_should_retry_ddg(self, exception, expected):
        assert _should_retry_ddg(exception) is expected

    def test_should_retry_ddg_no_response(self):
        """HTTPStatusError with response=None returns None (falsy)."""
        exc = httpx.HTTPStatusError("no resp", request=MagicMock(), response=None)
        # _should_retry_ddg returns None when response is None and the chain
        # short-circuits; None is falsy so retry won't happen
        assert not _should_retry_ddg(exc)


# ============================================================================
# ddg.py — _request_with_fallback backend paths
# ============================================================================


class TestRequestWithFallback:
    """Tests for the httpx→curl fallback logic."""

    def test_backend_curl_direct(self):
        """backend='curl' calls _fetch_curl directly."""
        with patch("web_search_mcp.ddg._fetch_curl") as mock_curl:
            mock_curl.return_value = "<html>curl</html>"
            result = _request_with_fallback("https://example.com", timeout=15, backend="curl")
            assert result == "<html>curl</html>"
            # _request_with_fallback calls _fetch_curl(url, timeout) with
            # timeout as a positional arg
            mock_curl.assert_called_once_with("https://example.com", 15)

    def test_backend_httpx_direct(self):
        """backend='httpx' calls _fetch_httpx directly (no fallback)."""
        with patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx:
            mock_httpx.return_value = "<html>httpx</html>"
            result = _request_with_fallback("https://example.com", timeout=15, backend="httpx")
            assert result == "<html>httpx</html>"
            mock_httpx.assert_called_once_with("https://example.com", 15)

    def test_backend_httpx_passes_cloudflare(self):
        """backend='httpx' does NOT fallback on Cloudflare (fixed backend)."""
        with patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx:
            mock_httpx.return_value = "<html>Just a moment...</html>"
            result = _request_with_fallback("https://example.com", timeout=15, backend="httpx")
            # Returns the Cloudflare page as-is because backend is fixed
            assert "Just a moment" in result
            mock_httpx.assert_called_once()

    def test_auto_backend_non_403_http_error(self):
        """auto backend with httpx 500 does NOT fallback to curl (tenacity retries then raises)."""
        with (
            patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx,
            patch("web_search_mcp.ddg._fetch_curl") as mock_curl,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_httpx.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response
            )
            # tenacity retries the 500 (it matches status >= 500) and after
            # 3 attempts raises RetryError (not the raw HTTPStatusError)
            with pytest.raises(tenacity.RetryError):
                _request_with_fallback("https://example.com", timeout=15, backend="auto")
            # Confirm curl was NOT called as fallback — httpx was retried instead
            mock_curl.assert_not_called()


# ============================================================================
# ddg.py — fetch_page edge cases
# ============================================================================


class TestFetchPageEdgeCases:
    """Edge cases in fetch_page not yet covered by existing tests."""

    def test_fetch_page_httpx_http_status_error(self):
        """HTTPStatusError returns an ErrorResponse."""
        with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "503", request=MagicMock(), response=mock_response
            )
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_httpx_request_error(self):
        """Transport-level RequestError returns ErrorResponse."""
        with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
            mock_fetch.side_effect = httpx.RequestError("connection refused")
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_curl_error(self):
        """CurlError returns ErrorResponse."""
        with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
            mock_fetch.side_effect = CurlError("curl failed", 7)
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_metadata_string_path(self):
        """include_metadata=True but trafilatura returns a single string (not tuple).
        The code sets metadata=None and issues a warning."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Content</body></html>"
            mock_extract.return_value = "Just string content"

            result = fetch_page("https://example.com", include_metadata=True)
            assert isinstance(result, PageResponse)
            assert result.content == "Just string content"
            assert result.metadata is None
            # metadata=None hits the warning branch
            assert result.warning == "Could not extract metadata."

    def test_fetch_page_metadata_tuple_none(self):
        """include_metadata=True and trafilatura returns a tuple with None metadata."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
        ):
            mock_fetch.return_value = "<html><body>Data</body></html>"
            mock_trafilatura.extract.return_value = ("Content text", None)

            result = fetch_page("https://example.com", include_metadata=True)
            assert isinstance(result, PageResponse)
            assert result.content == "Content text"
            assert result.warning == "Could not extract metadata."

    def test_fetch_page_metadata_tuple_empty_content(self):
        """include_metadata=True and trafilatura returns a tuple with empty content
        (tuple is truthy, passing the first gate; content is falsy, hitting the second)."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Data</body></html>"
            mock_extract.return_value = ("", {"title": "Empty"})

            result = fetch_page("https://example.com", include_metadata=True)
            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error

    def test_fetch_page_content_empty_after_extraction(self):
        """Extraction returns a non-None value but content is empty string."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Irrelevant</body></html>"
            mock_extract.return_value = ""

            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error

    def test_fetch_page_content_equals_max_length(self):
        """Content exactly at max_length boundary is returned."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Padding</body></html>"
            content = "A" * 100
            mock_extract.return_value = content

            result = fetch_page("https://example.com", max_length=100)
            assert isinstance(result, PageResponse)
            assert result.length == 100
            assert len(result.content) == 100

    def test_fetch_page_content_shorter_than_max_length(self):
        """Content shorter than max_length is not padded."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Short</body></html>"
            mock_extract.return_value = "Short text"

            result = fetch_page("https://example.com", max_length=10000)
            assert isinstance(result, PageResponse)
            assert result.content == "Short text"
            assert result.length == len("Short text")

    def test_fetch_page_httpx_error_on_download(self):
        """HTTPStatusError during httpx download is caught as fetch error."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "403", request=MagicMock(), response=mock_response
            )
            result = fetch_page("https://example.com/blocked")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_extraction_returns_none(self):
        """Trafilatura returns None → ErrorResponse."""
        with (
            patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
            patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body></body></html>"
            mock_extract.return_value = None

            result = fetch_page("https://example.com/blank")
            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error

    def test_fetch_page_generic_exception(self):
        """Non-HTTP exception in fetch_page returns ErrorResponse."""
        with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
            mock_fetch.side_effect = ValueError("conversion error")
            result = fetch_page("https://example.com/bad")
            assert isinstance(result, ErrorResponse)
            assert "conversion error" in result.error


# ============================================================================
# ddg.py — _fetch_httpx / _fetch_curl retry integration
# ============================================================================


class TestFetchInternals:
    """Internal fetch helpers invoked through the public fallback path."""

    def test_fetch_httpx_success(self):
        """_fetch_httpx returns text content."""
        with patch("web_search_mcp.ddg.http_client") as mock_client:
            mock_response = MagicMock()
            mock_response.text = "<html>OK</html>"
            mock_response.raise_for_status.return_value = None
            mock_client.get.return_value = mock_response

            result = _fetch_httpx("https://example.com", timeout=15)
            assert result == "<html>OK</html>"
            mock_client.get.assert_called_once_with("https://example.com", timeout=15)

    def test_fetch_curl_success(self):
        """_fetch_curl returns text content with Chrome impersonation."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html>curl OK</html>"
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.__enter__.return_value = mock_session

        with patch("web_search_mcp.ddg.curl_requests.Session", return_value=mock_session):
            result = _fetch_curl("https://example.com", timeout=30)
            assert result == "<html>curl OK</html>"
            mock_session.get.assert_called_once_with(
                "https://example.com", allow_redirects=True, timeout=30
            )

    def test_fetch_curl_failure(self):
        """_fetch_curl raises on failure."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock(status_code=403)
        )
        mock_session.get.return_value = mock_response
        mock_session.__enter__.return_value = mock_session

        with patch("web_search_mcp.ddg.curl_requests.Session", return_value=mock_session):
            with pytest.raises(httpx.HTTPStatusError):
                _fetch_curl("https://example.com", timeout=30)

    def test_auto_backend_httpx_failure_not_403(self):
        """auto backend with httpx 404 does NOT fallback to curl (tenacity
        does NOT retry 404, raising the httpx exception directly)."""
        with (
            patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx,
            patch("web_search_mcp.ddg._fetch_curl") as mock_curl,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_httpx.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=mock_response
            )
            # 404 is NOT retried by tenacity (_should_retry_ddg returns False),
            # so the raw httpx exception propagates on the first attempt
            with pytest.raises(httpx.HTTPStatusError):
                _request_with_fallback("https://example.com", timeout=15, backend="auto")
            mock_curl.assert_not_called()
