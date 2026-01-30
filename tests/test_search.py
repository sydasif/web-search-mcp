import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest

from web_search_mcp.providers.duckduckgo import DDGProvider
from web_search_mcp.search import ddg_search


class TestDDGSearch:
    """Test suite for DDG search functionality with mocked DDGProvider API calls."""

    @patch.object(DDGProvider, "search")
    def test_ddg_search_basic_text(self, mock_provider_search):
        """Test basic text search functionality."""
        mock_provider_search.return_value = {
            "query": "test query",
            "search_type": "text",
            "total_results": 1,
            "results": [
                {
                    "title": "Test Result",
                    "href": "https://example.com",
                    "body": "Test description",
                }
            ],
        }

        result = asyncio.run(ddg_search("test query", max_results=1))

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 1
        assert len(result["results"]) == 1
        mock_provider_search.assert_called_once_with(
            "test query",
            "text",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_with_time_filter(self, mock_provider_search):
        """Test search with time range filter."""
        mock_provider_search.return_value = {
            "query": "test query",
            "search_type": "text",
            "total_results": 0,
            "results": [],
        }

        result = asyncio.run(ddg_search("test query", time_range="d", max_results=2))

        assert result["search_type"] == "text"
        assert len(result["results"]) == 0
        mock_provider_search.assert_called_once_with(
            "test query",
            "text",
            max_results=2,
            time_range="d",
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_image_with_filters(self, mock_provider_search):
        """Test image search with advanced filters."""
        mock_result = {
            "query": "sunset",
            "search_type": "image",
            "total_results": 1,
            "results": [
                {
                    "title": "Test Image",
                    "image": "https://example.com/image.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "url": "https://example.com",
                    "height": 100,
                    "width": 200,
                    "source": "Bing",
                }
            ],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(
            ddg_search(
                "sunset",
                search_type="image",
                max_results=1,
                size="Large",
                color="Monochrome",
            )
        )

        assert result["search_type"] == "image"
        assert len(result["results"]) == 1
        assert "image" in result["results"][0]
        assert "thumbnail" in result["results"][0]
        mock_provider_search.assert_called_once_with(
            "sunset",
            "image",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
            size="Large",
            color="Monochrome",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_videos_with_filters(self, mock_provider_search):
        """Test video search with quality filters."""
        mock_result = {
            "query": "python tutorial",
            "search_type": "video",
            "total_results": 1,
            "results": [
                {
                    "title": "Test Video",
                    "content": "https://youtube.com/watch?v=test",
                    "description": "Test description",
                    "duration": "5:00",
                    "publisher": "YouTube",
                    "published": "2024-01-01",
                }
            ],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(
            ddg_search(
                "python tutorial",
                search_type="video",
                max_results=1,
                resolution="high",
                duration="medium",
            )
        )

        assert result["search_type"] == "video"
        assert len(result["results"]) == 1
        mock_provider_search.assert_called_once_with(
            "python tutorial",
            "video",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
            resolution="high",
            duration="medium",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_books(self, mock_provider_search):
        """Test books search functionality."""
        mock_result = {
            "query": "python programming",
            "search_type": "books",
            "total_results": 1,
            "results": [
                {
                    "title": "Python Programming",
                    "author": "Test Author",
                    "publisher": "2024",
                    "info": "English [en] · EPUB",
                    "url": "https://example.com/book",
                    "thumbnail": "https://example.com/thumb.jpg",
                }
            ],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(
            ddg_search("python programming", search_type="books", max_results=1)
        )

        assert result["search_type"] == "books"
        assert len(result["results"]) == 1
        assert "title" in result["results"][0]
        assert "author" in result["results"][0]
        mock_provider_search.assert_called_once_with(
            "python programming",
            "books",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_with_all_common_params(self, mock_provider_search):
        """Test search with all common parameters."""
        mock_result = {
            "query": "test query",
            "search_type": "news",
            "total_results": 0,
            "results": [],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(
            ddg_search(
                "test query",
                search_type="news",
                max_results=5,
                time_range="w",
                region="us-en",
                safesearch="off",
                page=2,
                backend="api",
            )
        )

        assert result["search_type"] == "news"
        mock_provider_search.assert_called_once_with(
            "test query",
            "news",
            max_results=5,
            time_range="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )

    @patch.object(DDGProvider, "search")
    def test_ddg_search_error_handling(self, mock_provider_search):
        """Test error handling when DDG API fails."""
        mock_provider_search.side_effect = Exception("Network error")

        result = asyncio.run(ddg_search("test query", max_results=1))

        assert result["query"] == "test query"
        assert result["search_type"] == "text"
        assert result["total_results"] == 0
        assert len(result["results"]) == 0
        assert "error" in result
        assert "Network error" in result["error"]

    @patch.object(DDGProvider, "search")
    def test_ddg_search_default_type(self, mock_provider_search):
        """Test that default search type is 'text'."""
        mock_result = {
            "query": "test",
            "search_type": "text",
            "total_results": 0,
            "results": [],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(ddg_search("test"))

        assert result["search_type"] == "text"
        # Check that it was called with search_type="text"
        call_args = mock_provider_search.call_args
        assert call_args[0][1] == "text"  # Second positional arg is search_type

    @patch.object(DDGProvider, "search")
    def test_ddg_search_none_params_not_passed(self, mock_provider_search):
        """Test that None parameters are not passed to DDG."""
        mock_result = {
            "query": "test",
            "search_type": "text",
            "total_results": 0,
            "results": [],
        }
        mock_provider_search.return_value = mock_result

        result = asyncio.run(
            ddg_search("test", max_results=5, time_range=None, region=None, page=1)
        )

        # Verify that only non-None parameters are passed
        call_kwargs = mock_provider_search.call_args[1]
        assert "max_results" in call_kwargs
        assert "time_range" not in call_kwargs  # None parameter should be filtered
        assert "region" not in call_kwargs  # None parameter should be filtered
        # But defaults should still be present
        assert "safesearch" in call_kwargs
        assert "backend" in call_kwargs
