from unittest.mock import patch

from web_search_mcp.models import SearchRequest
from web_search_mcp.search import ddg_search


class TestDDGSearch:
    """Test suite for DDG search functionality with mocked DDGS API calls."""

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_basic_text(self, mock_ddgs_class):
        """Test basic text search functionality."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {
                "title": "Test Result",
                "href": "https://example.com",
                "body": "Test description",
            }
        ]

        req = SearchRequest(query="test query", max_results=1)
        result = ddg_search(req)

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 1
        assert len(result["results"]) == 1
        mock_ddgs.text.assert_called_once_with(
            "test query",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_with_time_filter(self, mock_ddgs_class):
        """Test search with time range filter."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test query", time_range="d", max_results=2)
        result = ddg_search(req)

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

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_image_with_filters(self, mock_ddgs_class):
        """Test image search with advanced filters."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_result = [
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
        mock_ddgs.images.return_value = mock_result

        filters = {"size": "Large", "color": "Monochrome"}
        req = SearchRequest(
            query="sunset",
            search_type="image",
            max_results=1,
            filters=filters,
        )
        result = ddg_search(req)

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

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_videos_with_filters(self, mock_ddgs_class):
        """Test video search with quality filters."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_result = [
            {
                "title": "Test Video",
                "content": "https://youtube.com/watch?v=test",
                "description": "Test description",
                "duration": "5:00",
                "publisher": "YouTube",
                "published": "2024-01-01",
            }
        ]
        mock_ddgs.videos.return_value = mock_result

        filters = {"resolution": "high", "duration": "medium"}
        req = SearchRequest(
            query="python tutorial",
            search_type="video",
            max_results=1,
            filters=filters,
        )
        result = ddg_search(req)

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

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_books(self, mock_ddgs_class):
        """Test books search functionality."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_result = [
            {
                "title": "Python Programming",
                "author": "Test Author",
                "publisher": "2024",
                "info": "English [en] · EPUB",
                "url": "https://example.com/book",
                "thumbnail": "https://example.com/thumb.jpg",
            }
        ]
        mock_ddgs.books.return_value = mock_result

        req = SearchRequest(
            query="python programming",
            search_type="books",
            max_results=1,
        )
        result = ddg_search(req)

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

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_with_all_common_params(self, mock_ddgs_class):
        """Test search with all common parameters."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.news.return_value = []

        req = SearchRequest(
            query="test query",
            search_type="news",
            max_results=5,
            time_range="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )
        result = ddg_search(req)

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

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_error_handling(self, mock_ddgs_class):
        """Test error handling when DDG API fails."""
        mock_ddgs_class.return_value.__enter__.side_effect = Exception("Network error")

        req = SearchRequest(query="test query", max_results=1)
        result = ddg_search(req)

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 0
        assert len(result["results"]) == 0
        assert "error" in result
        assert "Network error" in result["error"]

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_default_type(self, mock_ddgs_class):
        """Test that default search type is 'text'."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test")
        result = ddg_search(req)

        assert result["search_type"] == "text"
        # Check that it was called with search_type="text"
        mock_ddgs.text.assert_called_once()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_none_params_not_passed(self, mock_ddgs_class):
        """Test that None parameters are not passed to DDG."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(
            query="test",
            max_results=5,
            time_range=None,
            region=None,
            page=1,
        )
        result = ddg_search(req)
        assert result["query"] == "test"
        assert result["search_type"] == "text"

        # Verify that only non-None parameters are passed
        call_kwargs = mock_ddgs.text.call_args[1]
        assert "max_results" in call_kwargs
        assert "timelimit" not in call_kwargs  # None parameter should be filtered
        assert "region" not in call_kwargs  # None parameter should be filtered
        # But defaults should still be present
        assert "safesearch" in call_kwargs

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_empty_query(self, mock_ddgs_class):
        """Test that an empty query returns an error."""
        req = SearchRequest(query="")
        result = ddg_search(req)

        assert "error" in result
        assert result["total_results"] == 0
        assert "Query cannot be empty" in result["error"]
        mock_ddgs_class.return_value.__enter__.return_value.text.assert_not_called()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_invalid_search_type(self, mock_ddgs_class):
        """Test that an invalid search_type returns an error."""
        req = SearchRequest(query="test", search_type="text")
        req.search_type = "invalid_type"  # type: ignore
        result = ddg_search(req)

        assert "error" in result
        assert "Unsupported search type: invalid_type" in result["error"]
        mock_ddgs_class.return_value.__enter__.return_value.text.assert_not_called()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_no_results(self, mock_ddgs_class):
        """Test that the search handles no results from the API."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="a very specific query with no results")
        result = ddg_search(req)

        assert result["total_results"] == 0
        assert len(result["results"]) == 0
        assert "error" not in result

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_max_results_zero(self, mock_ddgs_class):
        """Test that max_results=0 is handled correctly."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test", max_results=1)  # Create with valid value
        req.max_results = 0  # Set to 0 to bypass validation
        result = ddg_search(req)

        assert result["total_results"] == 0
        assert len(result["results"]) == 0
        mock_ddgs.text.assert_called_once_with(
            "test",
            max_results=0,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_malformed_api_response(self, mock_ddgs_class):
        """Test robustness against malformed API responses."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {"title": "Only title"},  # Missing href and body
            {"href": "https://example.com"},  # Missing title and body
        ]

        req = SearchRequest(query="test", max_results=2)
        result = ddg_search(req)

        assert "error" not in result
        assert result["total_results"] == 2
        assert len(result["results"]) == 2
        # Check that the available data is still parsed
        assert result["results"][0]["title"] == "Only title"
        assert result["results"][0].get("href") is None
        assert result["results"][1].get("title") is None
        assert result["results"][1]["href"] == "https://example.com"
