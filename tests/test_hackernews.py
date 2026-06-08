"""Tests for Hacker News search module."""

import unittest
from unittest.mock import patch, MagicMock

from web_search_mcp.hackernews import (
    search_hackernews,
    _compute_relevance,
    _title_matches_query,
    _flatten_query,
)


class TestHelpers(unittest.TestCase):
    """Tests for helper functions."""

    def test_flatten_query_removes_hyphens(self):
        assert _flatten_query("ts-bun-node") == "ts bun node"

    def test_flatten_query_removes_commas(self):
        assert _flatten_query("claude, personal agents") == "claude personal agents"

    def test_flatten_query_collapses_whitespace(self):
        assert _flatten_query("  hello   world  ") == "hello world"

    def test_title_matches_query_empty_query(self):
        assert _title_matches_query("Any title", "") is True

    def test_title_matches_query_strips_hn_prefix(self):
        assert _title_matches_query("Tell HN: Claude is amazing", "Claude") is True

    def test_title_matches_query_no_match(self):
        assert _title_matches_query("Go is faster than Rust", "Python") is False

    def test_title_matches_query_partial_token(self):
        assert _title_matches_query("Email is broken", "ai") is False

    def test_compute_relevance_empty_query(self):
        score = _compute_relevance("", "Some title", 0, 100)
        assert 0.0 <= score <= 1.0

    def test_compute_relevance_with_query(self):
        score = _compute_relevance("python async", "Python async library", 0, 50)
        assert 0.0 <= score <= 1.0
        assert score > 0.3

    def test_compute_relevance_higher_points_boost(self):
        low = _compute_relevance("python", "Python tips", 0, 5)
        high = _compute_relevance("python", "Python tips", 0, 5000)
        assert high >= low


class TestSearch(unittest.TestCase):
    """Tests for search_hackernews."""

    @patch("web_search_mcp.hackernews.httpx.get")
    def test_search_returns_items(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hits": [
                {
                    "objectID": "12345",
                    "title": "Claude 4 is released",
                    "url": "https://anthropic.com/blog",
                    "author": "dang",
                    "points": 150,
                    "num_comments": 80,
                    "created_at_i": 1749000000,
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        items = search_hackernews("Claude", depth="quick")
        assert len(items) >= 1
        assert items[0]["id"] == "12345"
        assert items[0]["title"] == "Claude 4 is released"

    @patch("web_search_mcp.hackernews.httpx.get")
    def test_search_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        items = search_hackernews("nonexistent topic xyz", depth="quick")
        assert items == []

    @patch("web_search_mcp.hackernews.httpx.get")
    def test_search_filters_mismatched_titles(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hits": [
                {
                    "objectID": "1",
                    "title": "Tell HN: Python is great",
                    "points": 10,
                    "num_comments": 2,
                    "created_at_i": 1749000000,
                },
                {
                    "objectID": "2",
                    "title": "Go tips for beginners",
                    "points": 5,
                    "num_comments": 1,
                    "created_at_i": 1749000000,
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        items = search_hackernews("Python")
        # Only the Python story should survive title filter
        assert len(items) == 1
        assert items[0]["id"] == "1"

    @patch("web_search_mcp.hackernews.httpx.get")
    def test_search_http_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        items = search_hackernews("test")
        assert items == []


if __name__ == "__main__":
    unittest.main()
