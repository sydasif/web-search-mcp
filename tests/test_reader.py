from unittest.mock import patch, MagicMock
import pytest
from web_search_mcp.models import ErrorResponse, PageResponse
from web_search_mcp.reader import (
    fetch_page,
    _fetch_httpx,
    _fetch_curl,
    _fetch_auto,
    _is_cloudflare_challenge_body,
    SUPPORTED_FETCH_BACKENDS,
)


def test_fetch_backend_constants():
    """Test that supported backends are defined correctly."""
    assert SUPPORTED_FETCH_BACKENDS == ("httpx", "curl", "auto")


def test_is_cloudflare_challenge_body():
    """Test Cloudflare challenge detection."""
    assert _is_cloudflare_challenge_body("") is False
    assert _is_cloudflare_challenge_body("Just a moment...") is True
    assert _is_cloudflare_challenge_body("cf-mitigated: challenge") is True
    assert _is_cloudflare_challenge_body("Checking your browser before accessing") is True
    assert _is_cloudflare_challenge_body("Normal webpage content") is False


def test_fetch_httpx_backend():
    """Test httpx backend fetches content correctly."""
    with patch("web_search_mcp.reader.http_client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        result = _fetch_httpx("https://example.com")
        assert result == "<html><body>Test</body></html>"
        mock_client.get.assert_called_once_with("https://example.com", timeout=30)


def test_fetch_curl_backend():
    """Test curl backend fetches content correctly."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html><body>Curl Test</body></html>"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    # Mock the context manager __enter__ to return the mock_session
    mock_session.__enter__.return_value = mock_session

    with patch("web_search_mcp.reader.curl_requests.Session", return_value=mock_session):
        result = _fetch_curl("https://example.com")
        assert result == "<html><body>Curl Test</body></html>"
        mock_session.get.assert_called_once()


def test_fetch_auto_backend_httpx_success():
    """Test auto backend uses httpx when successful."""
    with patch("web_search_mcp.reader._fetch_httpx") as mock_httpx:
        mock_httpx.return_value = "<html><body>Auto Test</body></html>"

        result = _fetch_auto("https://example.com")
        assert result == "<html><body>Auto Test</body></html>"
        mock_httpx.assert_called_once()


def test_fetch_auto_backend_fallback_on_403():
    """Test auto backend falls back to curl on 403."""
    import httpx as httpx_mod

    with (
        patch("web_search_mcp.reader._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.reader._fetch_curl") as mock_curl,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_httpx.side_effect = httpx_mod.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )
        mock_curl.return_value = "<html><body>Fallback</body></html>"

        result = _fetch_auto("https://example.com")
        assert result == "<html><body>Fallback</body></html>"
        mock_httpx.assert_called_once()
        mock_curl.assert_called_once()


def test_fetch_auto_backend_fallback_on_cloudflare():
    """Test auto backend falls back to curl on Cloudflare challenge."""
    with (
        patch("web_search_mcp.reader._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.reader._fetch_curl") as mock_curl,
    ):
        mock_httpx.return_value = "<html>Just a moment...</html>"
        mock_curl.return_value = "<html><body>Real Content</body></html>"

        result = _fetch_auto("https://example.com")
        assert result == "<html><body>Real Content</body></html>"
        mock_httpx.assert_called_once()
        mock_curl.assert_called_once()


def test_fetch_page_with_backend_parameter():
    """Test that fetch_page passes backend parameter correctly."""
    with (
        patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted Content"

        result = fetch_page("https://example.com", backend="curl")
        mock_fetch.assert_called_once_with("https://example.com", backend="curl", timeout=30)
        assert isinstance(result, PageResponse)
        assert "Extracted Content" in result.content


def test_fetch_page_with_auto_backend():
    """Test fetch_page with auto backend (default)."""
    with (
        patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted Content"

        result = fetch_page("https://example.com", backend="auto")
        mock_fetch.assert_called_once_with("https://example.com", backend="auto", timeout=30)
        assert isinstance(result, PageResponse)
        assert "Extracted Content" in result.content


def test_fetch_with_backend_unknown_raises():
    """Test that unknown backend raises ValueError."""
    from web_search_mcp.reader import _fetch_with_backend

    with pytest.raises(ValueError, match="Unknown fetch backend"):
        _fetch_with_backend("https://example.com", backend="unknown")


def test_fetch_curl_backend_custom_timeout():
    """Test curl backend with custom timeout."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html><body>Timeout Test</body></html>"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    # Mock the context manager __enter__ to return the mock_session
    mock_session.__enter__.return_value = mock_session

    with patch("web_search_mcp.reader.curl_requests.Session", return_value=mock_session):
        result = _fetch_curl("https://example.com", timeout=60)
        assert result == "<html><body>Timeout Test</body></html>"
        mock_session.get.assert_called_once_with(
            "https://example.com", allow_redirects=True, timeout=60
        )


def test_fetch_auto_backend_both_fail():
    """Test auto backend when both httpx and curl fail."""
    import httpx as httpx_mod

    with (
        patch("web_search_mcp.reader._fetch_httpx") as mock_httpx,
        patch("web_search_mcp.reader._fetch_curl") as mock_curl,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_httpx.side_effect = httpx_mod.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )
        mock_curl.side_effect = Exception("Curl also failed")

        from web_search_mcp.reader import _fetch_auto

        with pytest.raises(Exception, match="Curl also failed"):
            _fetch_auto("https://example.com")


def test_fetch_page_success():
    """Test successful page fetching and content extraction."""
    with (
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        # Mock trafilatura
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
    with patch("web_search_mcp.reader.http_client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        url = "https://example.com/empty"
        result = fetch_page(url)

        assert isinstance(result, ErrorResponse)
        assert "Could not download content" in result.error


def test_fetch_page_extraction_fails():
    """Test when content extraction returns None."""
    with (
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        mock_response = MagicMock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        mock_trafilatura.extract.return_value = None

        url = "https://example.com/empty"
        result = fetch_page(url)

        assert isinstance(result, ErrorResponse)
        assert "No readable text found" in result.error


def test_fetch_page_generic_exception():
    """Test handling of a generic exception during fetching."""
    with patch("web_search_mcp.reader.http_client") as mock_client:
        mock_client.get.side_effect = Exception("Network timeout")

        url = "https://example.com/timeout"
        result = fetch_page(url)

        assert isinstance(result, ErrorResponse)
        assert "Network timeout" in result.error


def test_fetch_page_with_metadata():
    """Test successful page fetching with metadata extraction."""
    with (
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.text = "<html><head><title>Test Title</title></head><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        # Mock metadata
        mock_metadata = MagicMock()
        mock_metadata.title = "Test Title"
        mock_metadata.author = "Test Author"
        mock_metadata.date = "2023-01-01"
        mock_metadata.description = "Test Description"
        mock_metadata.keywords = "test, keywords"
        mock_metadata.fingerprint = "abc123"

        # Mock trafilatura to return content and metadata
        mock_trafilatura.extract.return_value = ("Test Content", mock_metadata)

        url = "https://example.com"
        result = fetch_page(url, include_metadata=True)

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Test Content" in result.content
        assert result.metadata is not None
        assert result.metadata["title"] == "Test Title"
        assert result.metadata["author"] == "Test Author"
        mock_client.get.assert_called_once()
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_different_formats():
    """Test page fetching with different output formats."""
    with (
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        # Test default format (txt)
        mock_trafilatura.extract.return_value = "Test Content"

        url = "https://example.com"
        result = fetch_page(url)  # Uses default format

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "Test Content" in result.content
        mock_trafilatura.extract.assert_called_once()

        # Reset mock call count
        mock_trafilatura.extract.reset_mock()

        # Test markdown format
        mock_trafilatura.extract.return_value = "# Test\nContent"

        result = fetch_page(url, output_format="markdown")

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert "# Test" in result.content
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_content_options():
    """Test page fetching with different content inclusion options."""
    with (
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><table><tr><td>Table</td></tr></table><p>Content</p></body></html>"
        )
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        # Mock trafilatura
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
        patch("web_search_mcp.reader.http_client") as mock_client,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>" + "Content " * 1000 + "</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response

        # Mock trafilatura
        long_content = "Content " * 1000
        mock_trafilatura.extract.return_value = long_content

        url = "https://example.com"
        result = fetch_page(url, max_length=100)

        assert isinstance(result, PageResponse)
        assert result.url == url
        assert len(result.content) <= 100  # Should be truncated
        assert result.length == len(long_content)  # Original length preserved in metadata
        mock_trafilatura.extract.assert_called_once()


class TestFetchPageErrors:
    """Test suite for fetch_page error handling and edge cases."""

    def test_fetch_page_timeout(self):
        """Test handling of httpx.TimeoutException."""
        import httpx

        with patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Request timed out")
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "Request timed out after" in result.error

    def test_fetch_page_request_error(self):
        """Test handling of httpx.RequestError."""
        import httpx

        with patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch:
            mock_fetch.side_effect = httpx.ConnectError("Connection failed")
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_http_status_error(self):
        """Test handling of httpx.HTTPStatusError (e.g., 500)."""
        import httpx

        with patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed with status 500" in result.error

    def test_fetch_page_curl_error(self):
        """Test handling of CurlError."""
        from curl_cffi import CurlError

        with patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch:
            mock_fetch.side_effect = CurlError("Curl internal error")
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "HTTP request failed" in result.error

    def test_fetch_page_generic_exception(self):
        """Test handling of an unexpected exception."""
        with patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Something went wrong")
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "Something went wrong" in result.error

    def test_fetch_page_extraction_none(self):
        """Test when trafilatura.extract returns None."""
        with (
            patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch,
            patch("web_search_mcp.reader.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Empty</body></html>"
            mock_extract.return_value = None
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error

    def test_fetch_page_extraction_empty_string(self):
        """Test when trafilatura.extract returns an empty string."""
        with (
            patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch,
            patch("web_search_mcp.reader.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Empty</body></html>"
            mock_extract.return_value = ""
            result = fetch_page("https://example.com")
            assert isinstance(result, ErrorResponse)
            assert "No readable text found" in result.error

    def test_fetch_page_metadata_missing(self):
        """Test when include_metadata=True but no metadata is found."""
        with (
            patch("web_search_mcp.reader._fetch_with_backend") as mock_fetch,
            patch("web_search_mcp.reader.trafilatura.extract") as mock_extract,
        ):
            mock_fetch.return_value = "<html><body>Content</body></html>"
            # Return a tuple (content, metadata) where metadata is None
            mock_extract.return_value = ("Extracted Content", None)
            result = fetch_page("https://example.com", include_metadata=True)
            assert isinstance(result, PageResponse)
            assert result.warning == "Could not extract metadata."
            assert result.content == "Extracted Content"
