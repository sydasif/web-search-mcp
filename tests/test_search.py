import pytest
from unittest.mock import Mock, patch, MagicMock
from web_search_mcp.main import ddg_search


class TestDDGSearch:
    """Test suite for DDG search functionality with mocked DDGS API calls."""

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_basic_text(self, mock_ddgs_class):
        """Test basic text search functionality."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {
                "title": "Test Result",
                "href": "https://example.com",
                "body": "Test description",
            }
        ]
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("test query", max_results=1)

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 1
        assert len(result["results"]) == 1
        mock_ddgs.text.assert_called_once_with(
            "test query", max_results=1, safesearch="moderate", page=1, backend="auto"
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_with_time_filter(self, mock_ddgs_class):
        """Test search with time range filter."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("test query", time_range="d", max_results=2)

        assert result["search_type"] == "text"
        assert len(result["results"]) == 0
        mock_ddgs.text.assert_called_once_with(
            "test query",
            max_results=2,
            timelimit="d",
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_image_with_filters(self, mock_ddgs_class):
        """Test image search with advanced filters."""
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = [
            {
                "title": "Test Image",
                "image": "https://example.com/image.jpg",
                "thumbnail": "https://example.com/thumb.jpg",
                "url": "https://example.com",
                "height": 100,
                "width": 200,
                "source": "Bing",
            }
        ]
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search(
            "sunset",
            search_type="image",
            max_results=1,
            size="Large",
            color="Monochrome",
        )

        assert result["search_type"] == "image"
        assert len(result["results"]) == 1
        assert "image" in result["results"][0]
        assert "thumbnail" in result["results"][0]
        mock_ddgs.images.assert_called_once_with(
            "sunset",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
            size="Large",
            color="Monochrome",
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_videos_with_filters(self, mock_ddgs_class):
        """Test video search with quality filters."""
        mock_ddgs = MagicMock()
        mock_ddgs.videos.return_value = [
            {
                "title": "Test Video",
                "content": "https://youtube.com/watch?v=test",
                "description": "Test description",
                "duration": "5:00",
                "publisher": "YouTube",
                "published": "2024-01-01",
            }
        ]
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search(
            "python tutorial",
            search_type="video",
            max_results=1,
            resolution="high",
            duration="medium",
        )

        assert result["search_type"] == "video"
        assert len(result["results"]) == 1
        mock_ddgs.videos.assert_called_once_with(
            "python tutorial",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
            resolution="high",
            duration="medium",
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_books(self, mock_ddgs_class):
        """Test books search functionality."""
        mock_ddgs = MagicMock()
        mock_ddgs.books.return_value = [
            {
                "title": "Python Programming",
                "author": "Test Author",
                "publisher": "2024",
                "info": "English [en] · EPUB",
                "url": "https://example.com/book",
                "thumbnail": "https://example.com/thumb.jpg",
            }
        ]
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("python programming", search_type="books", max_results=1)

        assert result["search_type"] == "books"
        assert len(result["results"]) == 1
        assert "title" in result["results"][0]
        assert "author" in result["results"][0]
        mock_ddgs.books.assert_called_once_with(
            "python programming",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_with_all_common_params(self, mock_ddgs_class):
        """Test search with all common parameters."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search(
            "test query",
            search_type="news",
            max_results=5,
            time_range="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )

        assert result["search_type"] == "news"
        mock_ddgs.news.assert_called_once_with(
            "test query",
            max_results=5,
            timelimit="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_error_handling(self, mock_ddgs_class):
        """Test error handling when DDGS API fails."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.side_effect = Exception("Network error")
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("test query", max_results=1)

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 0
        assert len(result["results"]) == 0
        assert "error" in result
        assert "Network error" in result["error"]

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_default_type(self, mock_ddgs_class):
        """Test that default search type is 'text'."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("test")

        assert result["search_type"] == "text"
        mock_ddgs.text.assert_called_once()

    @patch("web_search_mcp.main.DDGS")
    def test_ddg_search_none_params_not_passed(self, mock_ddgs_class):
        """Test that None parameters are not passed to DDGS."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs

        result = ddg_search("test", max_results=5, time_range=None, region=None, page=1)

        # Verify that only non-None parameters are passed
        call_kwargs = mock_ddgs.text.call_args[1]
        assert "max_results" in call_kwargs
        assert "timelimit" not in call_kwargs
        assert "region" not in call_kwargs
        # But defaults should still be present
        assert "safesearch" in call_kwargs
        assert "backend" in call_kwargs
