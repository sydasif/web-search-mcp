"""Tests for Reddit search module."""

import unittest
from unittest.mock import patch

from web_search_mcp.reddit import reddit_search_tool
from web_search_mcp.models import ErrorResponse


class TestRedditSearch(unittest.TestCase):
    """Tests for reddit_search_tool."""

    def test_empty_query_returns_error(self):
        """Empty query should return error response."""
        result = reddit_search_tool("")
        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Query cannot be empty")

    def test_whitespace_query_returns_error(self):
        """Whitespace-only query should return error response."""
        result = reddit_search_tool("   ")
        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Query cannot be empty")

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_successful_search_returns_markdown(self, mock_search):
        """Successful search should return formatted markdown."""
        mock_search.return_value = [
            {
                "title": "Test Post",
                "url": "https://reddit.com/r/test/comments/abc123",
                "subreddit": "test",
                "score": 100,
                "num_comments": 25,
                "selftext": "This is a test post content",
                "top_comments": [
                    {"excerpt": "Great comment!", "score": 50, "author": "user1"},
                ],
                "date": "2026-01-15",
            }
        ]

        result = reddit_search_tool(
            "test query", max_results=5, depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        self.assertIn("Test Post", result)
        self.assertIn("r/test", result)
        self.assertIn("100 upvotes", result)
        self.assertIn("25 comments", result)
        self.assertIn("Great comment!", result)

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_successful_search_returns_json(self, mock_search):
        """Successful search with json format should return SearchResponse."""
        mock_search.return_value = [
            {
                "title": "Test Post",
                "url": "https://reddit.com/r/test/comments/abc123",
                "subreddit": "test",
                "score": 100,
                "num_comments": 25,
                "selftext": "Test content",
                "top_comments": [],
                "date": "2026-01-15",
            }
        ]

        result = reddit_search_tool(
            "test query", max_results=5, depth="quick", response_format="json"
        )

        from web_search_mcp.models import SearchResponse

        self.assertIsInstance(result, SearchResponse)
        self.assertEqual(result.query, "test query")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "Test Post")

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_time_range_mapping(self, mock_search):
        """Time range should be mapped to date filters."""
        mock_search.return_value = []

        result = reddit_search_tool(
            "test", time_range="w", depth="quick", response_format="markdown"
        )

        # Should not error
        self.assertIsInstance(result, str)
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertIn("from_date", call_args.kwargs)
        self.assertIn("to_date", call_args.kwargs)

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_subreddits_parameter(self, mock_search):
        """Subreddits parameter should be passed through."""
        mock_search.return_value = []

        result = reddit_search_tool(
            "test", subreddits=["Python", "learnpython"], depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertEqual(call_args.kwargs["subreddits"], ["Python", "learnpython"])

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_depth_limits_results(self, mock_search):
        """Depth parameter should cap max_results."""
        mock_search.return_value = [
            {
                "title": f"Post {i}",
                "url": f"https://r/{i}",
                "subreddit": "test",
                "score": 10,
                "num_comments": 5,
                "selftext": "",
                "top_comments": [],
                "date": "2026-01-01",
            }
            for i in range(10)  # search_and_enrich should return at most 10 for quick depth
        ]

        result = reddit_search_tool(
            "test", max_results=100, depth="quick", response_format="markdown"
        )

        # quick depth caps at 10
        self.assertIsInstance(result, str)
        self.assertIn("Found 10 posts", result)
        # Verify depth was passed to search_and_enrich
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertEqual(call_args.kwargs["depth"], "quick")

    @patch("web_search_mcp.reddit.reddit_search.search_and_enrich")
    def test_search_exception_returns_error(self, mock_search):
        """Exception during search should return error response."""
        mock_search.side_effect = Exception("Network error")

        result = reddit_search_tool("test query", response_format="markdown")

        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Reddit search failed")


if __name__ == "__main__":
    unittest.main()
