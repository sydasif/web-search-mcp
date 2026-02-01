from unittest.mock import patch
from web_search_mcp.reader import fetch_page


def test_fetch_page_success():
    """Test successful page fetching and content extraction."""
    with patch("web_search_mcp.reader.trafilatura") as mock_trafilatura:
        mock_trafilatura.fetch_url.return_value = (
            "<html><body><h1>Test</h1><p>Content</p></body></html>"
        )
        mock_trafilatura.extract.return_value = "Test Content"

        url = "https://example.com"
        result = fetch_page(url)

        assert result["url"] == url
        assert "Test Content" in result["content"]
        assert result["length"] == len("Test Content")
        mock_trafilatura.fetch_url.assert_called_once_with(url)
        mock_trafilatura.extract.assert_called_once()


def test_fetch_page_download_fails():
    """Test when the page download returns None."""
    with patch("web_search_mcp.reader.trafilatura") as mock_trafilatura:
        mock_trafilatura.fetch_url.return_value = None

        url = "https://example.com/404"
        result = fetch_page(url)

        assert "error" in result
        assert "Could not download content" in result["error"]


def test_fetch_page_extraction_fails():
    """Test when content extraction returns None."""
    with patch("web_search_mcp.reader.trafilatura") as mock_trafilatura:
        mock_trafilatura.fetch_url.return_value = "<html><body></body></html>"
        mock_trafilatura.extract.return_value = None

        url = "https://example.com/empty"
        result = fetch_page(url)

        assert "error" in result
        assert "No readable text found" in result["error"]


def test_fetch_page_generic_exception():
    """Test handling of a generic exception during fetching."""
    with patch("web_search_mcp.reader.trafilatura") as mock_trafilatura:
        mock_trafilatura.fetch_url.side_effect = Exception("Network timeout")

        url = "https://example.com/timeout"
        result = fetch_page(url)

        assert "error" in result
        assert "Network timeout" in result["error"]
