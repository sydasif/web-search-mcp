"""Tests for fetch_page and _request_with_fallback in ddg.py.

Covers: httpx success/failure, trafilatura success/failure, Exa fallback
paths, PDF detection, max_length truncation, metadata handling, and
error propagation.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from tenacity import RetryError

from web_search_mcp._models.responses import ErrorResponse, PageResponse
from web_search_mcp.search.ddg import _request_with_fallback, fetch_page

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HTML_CONTENT = "<html><body><p>Hello world</p></body></html>"
EXA_MARKDOWN = "# Hello world\n\nThis is clean markdown."


def _ok_response(text: str = HTML_CONTENT) -> httpx.Response:
    """Return a mock httpx.Response with status 200."""
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(status: int) -> httpx.Response:
    """Return a mock httpx.Response that raises on raise_for_status."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"{status}",
        request=MagicMock(),
        response=resp,
    )
    return resp


# ===========================================================================
# _request_with_fallback
# ===========================================================================


class TestRequestWithFallback:
    """Unit tests for _request_with_fallback."""

    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_success(self, mock_client: MagicMock) -> None:
        """httpx returns content — no Exa fallback."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)

        content, used_exa = _request_with_fallback("https://example.com")

        assert content == HTML_CONTENT
        assert used_exa is False

    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_fails_exa_succeeds(self, mock_client: MagicMock, mock_exa: MagicMock) -> None:
        """httpx raises HTTPStatusError — Exa fallback returns markdown."""
        mock_client.get.return_value = _error_response(403)

        content, used_exa = _request_with_fallback("https://example.com")

        assert content == EXA_MARKDOWN
        assert used_exa is True
        mock_exa.assert_called_once_with(["https://example.com"], timeout=30, max_chars=15000)

    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=None)
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_fails_exa_returns_none(
        self, mock_client: MagicMock, mock_exa: MagicMock
    ) -> None:
        """httpx raises (500 retries exhausted → RetryError), Exa returns None — re-raises."""
        mock_client.get.return_value = _error_response(500)

        with pytest.raises(RetryError):
            _request_with_fallback("https://example.com")

    @patch("web_search_mcp.search.ddg.exa_fetch", side_effect=RuntimeError("exa down"))
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_fails_exa_raises(self, mock_client: MagicMock, mock_exa: MagicMock) -> None:
        """httpx raises, Exa also raises — Exa exception propagates."""
        mock_client.get.return_value = _error_response(429)

        with pytest.raises(RuntimeError, match="exa down"):
            _request_with_fallback("https://example.com")

    @patch("web_search_mcp.search.ddg.exa_fetch", return_value="   ")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_fails_exa_returns_whitespace(
        self, mock_client: MagicMock, mock_exa: MagicMock
    ) -> None:
        """httpx raises, Exa returns whitespace — non-empty string is truthy, returned as content."""
        mock_client.get.return_value = _error_response(403)

        content, used_exa = _request_with_fallback("https://example.com")

        assert content == "   "
        assert used_exa is True

    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_timeout_error(self, mock_client: MagicMock) -> None:
        """httpx TimeoutException is caught and triggers Exa fallback."""
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN):
            content, used_exa = _request_with_fallback("https://example.com")
            assert content == EXA_MARKDOWN
            assert used_exa is True

    @patch("web_search_mcp.search.ddg.http_client")
    def test_retry_error_triggers_exa(self, mock_client: MagicMock) -> None:
        """tenacity RetryError (exhausted retries) triggers Exa fallback."""
        mock_client.get.side_effect = RetryError(last_attempt=MagicMock(exception=MagicMock))

        with patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN):
            content, used_exa = _request_with_fallback("https://example.com")
            assert content == EXA_MARKDOWN
            assert used_exa is True


# ===========================================================================
# fetch_page — happy paths
# ===========================================================================


class TestFetchPageHappy:
    """Happy-path tests for fetch_page."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_ok_trafilatura_ok(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx returns HTML, trafilatura extracts text → PageResponse."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = "Hello world"

        result = fetch_page("https://example.com")

        assert isinstance(result, PageResponse)
        assert result.content == "Hello world"
        assert result.url == "https://example.com"
        mock_trafilatura.extract.assert_called_once()

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_exa_used_directly_skips_trafilatura(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """When httpx fails and Exa succeeds, trafilatura is NOT called."""
        mock_client.get.return_value = _error_response(403)

        result = fetch_page("https://example.com")

        assert isinstance(result, PageResponse)
        assert result.content == EXA_MARKDOWN
        mock_trafilatura.extract.assert_not_called()


# ===========================================================================
# fetch_page — trafilatura failure → Exa second fallback
# ===========================================================================


class TestFetchPageTrafilaturaFallback:
    """Tests for the trafilatura-failure → Exa second-fallback path."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_returns_none_exa_succeeds(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura returns None → Exa fallback returns content."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://example.com")

        assert isinstance(result, PageResponse)
        assert result.content == EXA_MARKDOWN
        mock_exa.assert_called_once_with(["https://example.com"], timeout=30, max_chars=15000)

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_returns_empty_string_exa_succeeds(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura returns empty string → Exa fallback returns content."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = ""

        result = fetch_page("https://example.com")

        assert isinstance(result, PageResponse)
        assert result.content == EXA_MARKDOWN

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=None)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_fails_exa_returns_none(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Both trafilatura and Exa fail → error response."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value="")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_fails_exa_returns_empty(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura fails, Exa returns empty string → error response."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch(
        "web_search_mcp.search.ddg.exa_fetch",
        side_effect=RuntimeError("exa down"),
    )
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_fails_exa_raises(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura fails, Exa raises → error response (exception caught)."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=None)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_exa_receives_max_chars(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Exa fallback passes max_length as max_chars."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        fetch_page("https://example.com", max_length=5000)

        mock_exa.assert_called_once_with(["https://example.com"], timeout=30, max_chars=5000)


# ===========================================================================
# fetch_page — httpx failure paths
# ===========================================================================


class TestFetchPageHttpxFailure:
    """Tests for httpx failure → Exa first fallback path."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_403_exa_succeeds(
        self,
        mock_client: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx 403 → Exa fallback → PageResponse."""
        mock_client.get.return_value = _error_response(403)

        result = fetch_page("https://example.com")

        assert isinstance(result, PageResponse)
        assert result.content == EXA_MARKDOWN

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=None)
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_500_exa_fails(
        self,
        mock_client: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx 500, Exa also fails → error response."""
        mock_client.get.return_value = _error_response(500)

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "HTTP request failed" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_httpx_timeout_caught(
        self,
        mock_client: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx TimeoutException with no Exa → error response."""
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with patch("web_search_mcp.search.ddg.exa_fetch", return_value=None):
            result = fetch_page("https://example.com")

            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_retry_error_caught(
        self,
        mock_client: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """tenacity RetryError with no Exa → error response."""
        mock_client.get.side_effect = RetryError(last_attempt=MagicMock(exception=MagicMock()))

        with patch("web_search_mcp.search.ddg.exa_fetch", return_value=None):
            result = fetch_page("https://example.com")

            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error


# ===========================================================================
# fetch_page — empty content
# ===========================================================================


class TestFetchPageEmptyContent:
    """Tests for empty/None raw content."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_raw_content_none(
        self,
        mock_client: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx returns None content → error."""
        mock_response = MagicMock()
        mock_response.text = None
        mock_client.get.return_value = mock_response

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "Could not download content" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_raw_content_empty_string(
        self,
        mock_client: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """httpx returns empty string → error."""
        mock_client.get.return_value = _ok_response("")

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "Could not download content" in result.error


# ===========================================================================
# fetch_page — PDF detection
# ===========================================================================


class TestFetchPagePdf:
    """Tests for PDF URL detection and extraction."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg._fetch_pdf_text", return_value="PDF content here")
    def test_pdf_url_dot_pdf(
        self,
        mock_pdf: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """URL ending in .pdf → PDF extraction."""
        result = fetch_page("https://example.com/file.pdf")

        assert isinstance(result, PageResponse)
        assert result.content == "PDF content here"
        mock_pdf.assert_called_once()

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg._fetch_pdf_text", return_value="PDF content here")
    def test_pdf_url_path_contains_pdf(
        self,
        mock_pdf: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """URL with /pdf/ in path → PDF extraction."""
        result = fetch_page("https://example.com/papers/document.pdf")

        assert isinstance(result, PageResponse)
        assert result.content == "PDF content here"

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg._fetch_pdf_text", return_value="PDF content here")
    def test_pdf_url_query_param(
        self,
        mock_pdf: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """URL with pdf= query param → PDF extraction."""
        result = fetch_page("https://example.com/view?pdf=123")

        assert isinstance(result, PageResponse)
        assert result.content == "PDF content here"

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg._fetch_pdf_text", return_value=None)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_pdf_fails_falls_through_to_html(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_pdf: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """PDF extraction fails → falls through to normal HTML path."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = "Extracted text"

        result = fetch_page("https://example.com/file.pdf")

        assert isinstance(result, PageResponse)
        assert result.content == "Extracted text"
        mock_trafilatura.extract.assert_called_once()


# ===========================================================================
# fetch_page — max_length truncation
# ===========================================================================


class TestFetchPageMaxLength:
    """Tests for max_length truncation."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_result_truncated(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura result is truncated to max_length."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = "A" * 20000

        result = fetch_page("https://example.com", max_length=5000)

        assert isinstance(result, PageResponse)
        assert len(result.content) == 5000
        assert result.length == 20000

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value="B" * 20000)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_exa_fallback_result_truncated(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Exa fallback result is truncated to max_length."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://example.com", max_length=5000)

        assert isinstance(result, PageResponse)
        assert len(result.content) == 5000

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value="C" * 20000)
    @patch("web_search_mcp.search.ddg.http_client")
    def test_exa_direct_result_truncated(
        self,
        mock_client: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Exa first-fallback result is truncated to max_length."""
        mock_client.get.return_value = _error_response(403)

        result = fetch_page("https://example.com", max_length=3000)

        assert isinstance(result, PageResponse)
        assert len(result.content) == 3000


# ===========================================================================
# fetch_page — metadata
# ===========================================================================


class TestFetchPageMetadata:
    """Tests for include_metadata behavior."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_metadata_extracted(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """include_metadata=True extracts metadata when available."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_metadata = MagicMock()
        mock_metadata.title = "Test Title"
        mock_metadata.author = "Test Author"
        mock_metadata.date = "2026-01-01"
        mock_metadata.description = "A description"
        mock_metadata.fingerprint = "abc123"
        mock_trafilatura.extract.return_value = ("Hello", mock_metadata)

        result = fetch_page("https://example.com", include_metadata=True)

        assert isinstance(result, PageResponse)
        assert result.content == "Hello"
        assert result.metadata is not None
        assert result.metadata["title"] == "Test Title"
        assert result.metadata["author"] == "Test Author"

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_metadata_not_extracted(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """include_metadata=False does not extract metadata."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = "Hello"

        result = fetch_page("https://example.com", include_metadata=False)

        assert isinstance(result, PageResponse)
        assert result.metadata is None

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_metadata_requested_but_none_available(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """include_metadata=True but no metadata returned → warning."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = ("Hello", None)

        result = fetch_page("https://example.com", include_metadata=True)

        assert isinstance(result, PageResponse)
        assert result.warning == "Could not extract metadata."


# ===========================================================================
# fetch_page — exception handling
# ===========================================================================


class TestFetchPageExceptionHandling:
    """Tests for unexpected exception handling."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_unexpected_exception_caught(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Unexpected exception (not httpx) → error response."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.side_effect = RuntimeError("something broke")

        result = fetch_page("https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "something broke" in result.error

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_content_after_metadata_empty(
        self,
        mock_client: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """trafilatura returns tuple with empty content → error."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)

        with patch("web_search_mcp.search.ddg.trafilatura") as mock_trafilatura:
            mock_trafilatura.extract.return_value = ("", None)

            result = fetch_page("https://example.com", include_metadata=True)

            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error


# ===========================================================================
# fetch_page — JSON/non-HTML content (the original bug scenario)
# ===========================================================================


class TestFetchPageNonHtmlContent:
    """Tests for non-HTML content like JSON APIs (e.g. wttr.in)."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=EXA_MARKDOWN)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_json_content_trafilatura_fails_exa_succeeds(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """JSON API: httpx succeeds, trafilatura can't extract → Exa fallback."""
        json_content = '{"current_condition": [{"temp_C": "22"}]}'
        mock_client.get.return_value = _ok_response(json_content)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://wttr.in/test.format=j1")

        assert isinstance(result, PageResponse)
        assert result.content == EXA_MARKDOWN
        mock_exa.assert_called_once()

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch", return_value=None)
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_json_content_trafilatura_and_exa_both_fail(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """JSON API: both trafilatura and Exa fail → error response."""
        json_content = '{"error": "not found"}'
        mock_client.get.return_value = _ok_response(json_content)
        mock_trafilatura.extract.return_value = None

        result = fetch_page("https://api.example.com/missing")

        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error


# ===========================================================================
# fetch_page — pass-through parameters
# ===========================================================================


class TestFetchPageParameters:
    """Tests for parameter pass-through to trafilatura."""

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_trafilatura_receives_all_params(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """All trafilatura parameters are passed through correctly."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = "text"

        fetch_page(
            "https://example.com",
            output_format="markdown",
            include_metadata=True,
            include_tables=True,
            deduplicate=False,
        )

        mock_trafilatura.extract.assert_called_once_with(
            HTML_CONTENT,
            output_format="markdown",
            with_metadata=True,
            include_tables=True,
            include_links=True,
            deduplicate=False,
        )

    @patch("web_search_mcp.search.ddg.fetch_rate_limiter")
    @patch("web_search_mcp.search.ddg.exa_fetch")
    @patch("web_search_mcp.search.ddg.trafilatura")
    @patch("web_search_mcp.search.ddg.http_client")
    def test_exa_timeout_matches_fetch_page_timeout(
        self,
        mock_client: MagicMock,
        mock_trafilatura: MagicMock,
        mock_exa: MagicMock,
        mock_limiter: MagicMock,
    ) -> None:
        """Exa fallback uses the same timeout as fetch_page."""
        mock_client.get.return_value = _ok_response(HTML_CONTENT)
        mock_trafilatura.extract.return_value = None
        mock_exa.return_value = None

        fetch_page("https://example.com", timeout=15)

        mock_exa.assert_called_once_with(["https://example.com"], timeout=15, max_chars=15000)
