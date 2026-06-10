from unittest.mock import patch, MagicMock
import pytest
from web_search_mcp.models import ErrorResponse, PageResponse
from web_search_mcp.ddg import (
    fetch_page,
    _fetch_httpx,
    _fetch_curl,
    _request_with_fallback,
    _is_cloudflare_challenge_body,
)


def test_is_cloudflare_challenge_body():
    """Test Cloudflare challenge detection."""
    assert _is_cloudflare_challenge_body("") is False
    assert _is_cloudflare_challenge_body("Just a moment...") is True
    assert _is_cloudflare_challenge_body("cf-mitigated: challenge") is True
    assert _is_cloudflare_challenge_body("Checking your browser before accessing") is True
    assert _is_cloudflare_challenge_body("Normal webpage content") is False


def test_fetch_httpx_backend():
    """Test httpx backend fetches content correctly."""
    with patch("web_search_mcp.ddg.http_client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        result = _fetch_httpx("https://example.com", timeout=30)
        assert result == "<html><body>Test</body></html>"
        mock_client.get.assert_called_once_with("https://example.com", timeout=30)


def test_fetch_curl_backend():
    """Test curl backend fetches content correctly."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html><body>Curl Test</body></html>"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    mock_session.__enter__.return_value = mock_session

    with patch("web_search_mcp.ddg.curl_requests.Session", return_value=mock_session):
        result = _fetch_curl("https://example.com", timeout=30)
        assert result == "<html><body>Curl Test</body></html>"
        mock_session.get.assert_called_once()


def test_fetch_auto_backend_httpx_success():
    """Test auto backend uses httpx when successful."""
    with patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx:
        mock_httpx.return_value = "<html><body>Auto Test</body></html>"

        result = _request_with_fallback("https://example.com", timeout=30)
        assert result == "<html><body>Auto Test</body></html>"
        mock_httpx.assert_called_once()


def test_fetch_auto_backend_fallback_on_403():
    """Test auto backend falls back to curl on 403."""
    import httpx as httpx_mod

    with (
        patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.ddg._fetch_curl") as mock_curl,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_httpx.side_effect = httpx_mod.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )
        mock_curl.return_value = "<html><body>Fallback</body></html>"

        result = _request_with_fallback("https://example.com", timeout=30)
        assert result == "<html><body>Fallback</body></html>"
        mock_httpx.assert_called_once()
        mock_curl.assert_called_once()


def test_fetch_auto_backend_fallback_on_cloudflare():
    """Test auto backend falls back to curl on Cloudflare challenge."""
    with (
        patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.ddg._fetch_curl") as mock_curl,
    ):
        mock_httpx.return_value = "<html>Just a moment...</html>"
        mock_curl.return_value = "<html><body>Real Content</body></html>"

        result = _request_with_fallback("https://example.com", timeout=30)
        assert result == "<html><body>Real Content</body></html>"
        mock_httpx.assert_called_once()
        mock_curl.assert_called_once()


def test_fetch_page_with_backend_parameter():
    """Test that fetch_page passes backend parameter correctly."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted Content"

        result = fetch_page("https://example.com", backend="curl")
        mock_fetch.assert_called_once_with("https://example.com", timeout=30, backend="curl")
        assert isinstance(result, PageResponse)
        assert "Extracted Content" in result.content


def test_fetch_page_with_auto_backend():
    """Test fetch_page with auto backend (default)."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted Content"

        result = fetch_page("https://example.com", backend="auto")
        mock_fetch.assert_called_once_with("https://example.com", timeout=30, backend="auto")
        assert isinstance(result, PageResponse)
        assert "Extracted Content" in result.content


def test_fetch_curl_backend_custom_timeout():
    """Test curl backend with custom timeout."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html><body>Timeout Test</body></html>"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    mock_session.__enter__.return_value = mock_session

    with patch("web_search_mcp.ddg.curl_requests.Session", return_value=mock_session):
        result = _fetch_curl("https://example.com", timeout=60)
        assert result == "<html><body>Timeout Test</body></html>"
        mock_session.get.assert_called_once_with(
            "https://example.com", allow_redirects=True, timeout=60
        )


def test_fetch_auto_backend_both_fail():
    """Test auto backend when both httpx and curl fail."""
    import httpx as httpx_mod

    with (
        patch("web_search_mcp.ddg._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.ddg._fetch_curl") as mock_curl,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_httpx.side_effect = httpx_mod.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )
        mock_curl.side_effect = Exception("Curl also failed")

        # We use _request_with_fallback directly
        with pytest.raises(Exception, match="Curl also failed"):
            _request_with_fallback("https://example.com", timeout=30)


def test_fetch_page_success():
    """Test successful page fetching and content extraction."""
    with (
        patch("web_search_mcp.ddg.http_client") as mock_client,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        mock_trafilatura.extract.return_value = "Test Content"

        url = "https://example.com"
        result = fetch_page(url)

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Test Content" in result.content
        assert result.length == len("Test Content")
        mock_client.get.assert_called_once()
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_download_fails():
    """Test when the page download returns empty content."""
    with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
        mock_fetch.return_value = ""
        result = fetch_page("https://example.com/empty")
        assert isinstance(result, ErrorResponse)
        assert "Could not download content" in result.error


def test_fetch_page_extraction_fails():
    """Test when content extraction returns None."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura.extract") as mock_extract,
    ):
        mock_fetch.return_value = "<html><body>Empty</body></html>"
        mock_extract.return_value = None
        result = fetch_page("https://example.com/empty")
        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error


def test_fetch_page_generic_exception():
    """Test handling of a generic exception during fetching."""
    with patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch:
        mock_fetch.side_effect = Exception("Network timeout")
        result = fetch_page("https://example.com/timeout")
        assert isinstance(result, ErrorResponse)
        assert "Network timeout" in result.error


def test_fetch_page_with_metadata():
    """Test successful page fetching with metadata extraction."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><head><title>Test Title</title></head><body><h1>Test</h1><p>Content</p></body></html>"
        mock_metadata = MagicMock()
        mock_metadata.title = "Test Title"
        mock_metadata.author = "Test Author"
        mock_metadata.date = "2023-01-01"
        mock_metadata.description = "Test Description"
        mock_metadata.fingerprint = "abc123"
        mock_trafilatura.extract.return_value = ("Test Content", mock_metadata)

        url = "https://example.com"
        result = fetch_page(url, include_metadata=True)

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Test Content" in result.content
        assert result.metadata is not None
        assert result.metadata["title"] == "Test Title"
        assert result.metadata["author"] == "Test Author"
        mock_fetch.assert_called_once()
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_different_formats():
    """Test page fetching with different output formats."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_trafilatura.extract.return_value = "Test Content"

        url = "https://example.com"
        result = fetch_page(url)
        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Test Content" in result.content
        mock_trafilatura.extract.assert_called_once()

        mock_trafilatura.extract.reset_mock()
        mock_trafilatura.extract.return_value = "# Test\nContent"
        result = fetch_page(url, output_format="markdown")
        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "# Test" in result.content
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_content_options():
    """Test page fetching with different content inclusion options."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = (
            "<html><body><table><tr><td>Table</td></tr></table><p>Content</p></body></html>"
        )
        mock_trafilatura.extract.return_value = "Content with tables and comments"

        url = "https://example.com"
        result = fetch_page(url, include_tables=True, include_comments=True)
        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Content with tables and comments" in result.content
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_max_length():
    """Test page fetching with length limitation."""
    with (
        patch("web_search_mcp.ddg._request_with_fallback") as mock_fetch,
        patch("web_search_mcp.ddg.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body><p>" + "Content " * 1000 + "</p></body></html>"
        mock_trafilatura.extract.return_value = "Content " * 1000

        url = "https://example.com"
        result = fetch_page(url, max_length=100)
        assert isinstance(result, PageResponse)
        assert result.url == url
        assert len(result.content) <= 100
        assert result.length == len("Content " * 1000)
        mock_trafilatura.extract.assert_called_once()
