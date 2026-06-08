"""Tests for GitHub search module."""

import unittest
from unittest.mock import patch

from web_search_mcp.github import (
    search_github,
    enrich_with_comments,
    _compute_relevance,
    _parse_repo_from_url,
    _parse_date,
)


class TestHelpers(unittest.TestCase):
    """Tests for helper functions."""

    def test_parse_repo_from_url_standard(self):
        assert _parse_repo_from_url("https://github.com/owner/repo/issues/1") == "owner/repo"

    def test_parse_repo_from_url_pr(self):
        assert _parse_repo_from_url("https://github.com/owner/repo/pull/42") == "owner/repo"

    def test_parse_repo_from_url_invalid(self):
        assert _parse_repo_from_url("https://github.com/owner") == ""

    def test_parse_date_iso(self):
        assert _parse_date("2026-06-01T12:00:00Z") == "2026-06-01"

    def test_parse_date_none(self):
        assert _parse_date(None) is None

    def test_parse_date_empty(self):
        assert _parse_date("") is None

    def test_parse_date_malformed(self):
        assert _parse_date("not-a-date") == "not-a-date"[:10]

    def test_compute_relevance_empty_query(self):
        score = _compute_relevance("", "Some title", 0, 50, 10)
        assert 0.0 <= score <= 1.0

    def test_compute_relevance_with_query(self):
        score = _compute_relevance("uv package", "uv package manager", 0, 100, 20)
        assert score > 0.3

    def test_compute_relevance_higher_reactions_boost(self):
        low = _compute_relevance("rust", "Rust compiler", 0, 5, 0)
        high = _compute_relevance("rust", "Rust compiler", 0, 500, 100)
        assert high >= low


class TestSearch(unittest.TestCase):
    """Tests for search_github."""

    @patch("web_search_mcp.github._resolve_token")
    @patch("web_search_mcp.github._fetch_json")
    def test_search_returns_items(self, mock_fetch, mock_token):
        mock_token.return_value = "ghp_test123"
        mock_fetch.return_value = {
            "items": [
                {
                    "html_url": "https://github.com/astral-sh/uv/issues/1",
                    "title": "Add feature X",
                    "body": "This is a feature request",
                    "reactions": {"total_count": 42},
                    "comments": 10,
                    "state": "open",
                    "labels": [{"name": "enhancement"}],
                    "user": {"login": "testuser"},
                    "created_at": "2026-06-01T12:00:00Z",
                }
            ]
        }

        items = search_github("uv feature", depth="quick")
        assert len(items) >= 1
        assert items[0]["title"] == "Add feature X"
        assert items[0]["repository"] == "astral-sh/uv"
        assert items[0]["is_pr"] is False
        assert items[0]["engagement"]["reactions"] == 42

    @patch("web_search_mcp.github._resolve_token")
    def test_search_no_token_returns_empty(self, mock_token):
        mock_token.return_value = None
        items = search_github("test")
        assert items == []

    @patch("web_search_mcp.github._resolve_token")
    @patch("web_search_mcp.github._fetch_json")
    def test_search_empty_response(self, mock_fetch, mock_token):
        mock_token.return_value = "ghp_test123"
        mock_fetch.return_value = {"items": []}

        items = search_github("nonexistent", depth="quick")
        assert items == []

    @patch("web_search_mcp.github._resolve_token")
    @patch("web_search_mcp.github._fetch_json")
    def test_search_http_error(self, mock_fetch, mock_token):
        mock_token.return_value = "ghp_test123"
        mock_fetch.return_value = None

        items = search_github("test")
        assert items == []

    @patch("web_search_mcp.github._resolve_token")
    @patch("web_search_mcp.github._fetch_json")
    def test_search_detects_pr(self, mock_fetch, mock_token):
        mock_token.return_value = "ghp_test123"
        mock_fetch.return_value = {
            "items": [
                {
                    "html_url": "https://github.com/astral-sh/uv/pull/42",
                    "title": "Fix bug",
                    "body": "Fixes a bug",
                    "pull_request": {"url": "..."},
                    "reactions": {"total_count": 5},
                    "comments": 2,
                    "state": "open",
                    "labels": [],
                    "user": {"login": "testuser"},
                    "created_at": "2026-06-01T12:00:00Z",
                }
            ]
        }

        items = search_github("fix bug", depth="quick")
        assert len(items) >= 1
        assert items[0]["is_pr"] is True


class TestEnrich(unittest.TestCase):
    """Tests for enrich_with_comments."""

    @patch("web_search_mcp.github._resolve_token")
    @patch("web_search_mcp.github._fetch_json")
    def test_enrich_top_items(self, mock_fetch, mock_token):
        mock_token.return_value = "ghp_test123"
        mock_fetch.return_value = [
            {
                "body": "Great suggestion!",
                "reactions": {"total_count": 10},
                "user": {"login": "commenter1"},
            }
        ]

        items = [
            {
                "title": "Feature X",
                "url": "https://github.com/astral-sh/uv/issues/1",
                "engagement": {"reactions": 42, "comments": 5},
            }
        ]
        result = enrich_with_comments(items, depth="quick")
        assert "top_comments" in result[0]
        assert result[0]["top_comments"][0]["author"] == "commenter1"

    @patch("web_search_mcp.github._resolve_token")
    def test_enrich_no_token(self, mock_token):
        mock_token.return_value = None
        items = [{"title": "Test", "url": "https://github.com/owner/repo/issues/1"}]
        result = enrich_with_comments(items)
        assert result == items  # unchanged

    def test_enrich_empty_items(self):
        assert enrich_with_comments([]) == []


if __name__ == "__main__":
    unittest.main()
