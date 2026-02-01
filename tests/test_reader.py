from unittest.mock import patch, MagicMock
from web_search_mcp.reader import fetch_page


def test_fetch_page_success():
    """Test successful page fetching and content extraction."""
    with (
        patch("web_search_mcp.reader.httpx.get") as mock_get,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock trafilatura
        mock_trafilatura.extract.return_value = "Test Content"

        url = "https://example.com"
        result = fetch_page(url)

        assert result["url"] == url
        assert "Test Content" in result["content"]
        assert result["length"] == len("Test Content")
        mock_get.assert_called_once()
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_download_fails():
    """Test when the page download returns empty content."""
    with patch("web_search_mcp.reader.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        url = "https://example.com/empty"
        result = fetch_page(url)

        assert "error" in result
        assert "Could not download content" in result["error"]


def test_fetch_page_extraction_fails():
    """Test when content extraction returns None."""
    with (
        patch("web_search_mcp.reader.httpx.get") as mock_get,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        mock_response = MagicMock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        mock_trafilatura.extract.return_value = None

        url = "https://example.com/empty"
        result = fetch_page(url)

        assert "error" in result
        assert "No readable text found" in result["error"]


def test_fetch_page_generic_exception():
    """Test handling of a generic exception during fetching."""
    with patch("web_search_mcp.reader.httpx.get") as mock_get:
        mock_get.side_effect = Exception("Network timeout")

        url = "https://example.com/timeout"
        result = fetch_page(url)

        assert "error" in result
        assert "Network timeout" in result["error"]


def test_fetch_page_with_metadata():
    """Test successful page fetching with metadata extraction."""
    with (
        patch("web_search_mcp.reader.httpx.get") as mock_get,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
        patch("web_search_mcp.reader.trafilatura.extract_metadata") as mock_extract_metadata,
    ):
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.text = "<html><head><title>Test Title</title></head><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock trafilatura
        mock_trafilatura.extract.return_value = "Test Content"

        # Mock metadata
        mock_metadata = MagicMock()
        mock_metadata.title = "Test Title"
        mock_metadata.author = "Test Author"
        mock_metadata.date = "2023-01-01"
        mock_metadata.description = "Test Description"
        mock_metadata.keywords = "test, keywords"
        mock_metadata.fingerprint = "abc123"
        mock_extract_metadata.return_value = mock_metadata

        url = "https://example.com"
        result = fetch_page(url, include_metadata=True)

        assert result["url"] == url
        assert "Test Content" in result["content"]
        assert "metadata" in result
        assert result["metadata"]["title"] == "Test Title"
        assert result["metadata"]["author"] == "Test Author"
        mock_get.assert_called_once()
        mock_trafilatura.extract.assert_called_once()
        mock_extract_metadata.assert_called_once()


def test_fetch_page_with_different_formats():
    """Test page fetching with different output formats."""
    with (
        patch("web_search_mcp.reader.httpx.Client") as mock_client_class,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test markdown format
        mock_trafilatura.extract.return_value = "# Test\nContent"

        url = "https://example.com"
        result = fetch_page(url, output_format="markdown")

        assert result["url"] == url
        assert "# Test" in result["content"]
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_content_options():
    """Test page fetching with different content inclusion options."""
    with (
        patch("web_search_mcp.reader.httpx.Client") as mock_client_class,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><table><tr><td>Table</td></tr></table><p>Content</p></body></html>"
        )
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Mock trafilatura
        mock_trafilatura.extract.return_value = "Content with tables and comments"

        url = "https://example.com"
        result = fetch_page(url, include_tables=True, include_comments=True)

        assert result["url"] == url
        assert "Content with tables and comments" in result["content"]
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_with_max_length():
    """Test page fetching with length limitation."""
    with (
        patch("web_search_mcp.reader.httpx.Client") as mock_client_class,
        patch("web_search_mcp.reader.trafilatura") as mock_trafilatura,
    ):
        # Mock HTTP client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>" + "Content " * 1000 + "</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Mock trafilatura
        long_content = "Content " * 1000
        mock_trafilatura.extract.return_value = long_content

        url = "https://example.com"
        result = fetch_page(url, max_length=100)

        assert result["url"] == url
        assert len(result["content"]) <= 100  # Should be truncated
        assert result["length"] == len(long_content)  # Original length preserved in metadata
        mock_trafilatura.extract.assert_called_once()
