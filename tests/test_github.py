"""Tests for GitHub search module."""

import json
import subprocess
import unittest
from unittest.mock import patch

from web_search_mcp.github import (
    search_github,
    enrich_with_comments,
    _compute_relevance,
    _parse_repo_from_url,
    _parse_date,
    parse_github_url as _parse_url,
    _sum_reactions,
    _render_reactions_bar,
    render_issue_markdown,
    get_github_issue,
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


class TestGetIssue(unittest.TestCase):
    """Tests for parse_github_url and get_github_issue."""

    def test_parse_issue_url(self):
        owner, repo, number, kind = _parse_url("https://github.com/astral-sh/uv/issues/42")
        assert owner == "astral-sh"
        assert repo == "uv"
        assert number == 42
        assert kind == "issue"

    def test_parse_pr_url(self):
        owner, repo, number, kind = _parse_url("https://github.com/python/cpython/pull/100000")
        assert owner == "python"
        assert repo == "cpython"
        assert number == 100000
        assert kind == "pr"

    def test_parse_url_with_trailing_slash(self):
        owner, repo, number, kind = _parse_url("https://github.com/owner/repo/issues/5/")
        assert (owner, repo, number, kind) == ("owner", "repo", 5, "issue")

    def test_parse_url_invalid_host(self):
        with self.assertRaises(ValueError):
            _parse_url("https://gitlab.com/owner/repo/issues/1")

    def test_parse_url_no_match(self):
        with self.assertRaises(ValueError):
            _parse_url("https://github.com/owner/repo")

    def test_parse_url_bad_path(self):
        with self.assertRaises(ValueError):
            _parse_url("https://github.com/owner/repo/wiki/Home")

    def test_sum_reactions_empty(self):
        assert _sum_reactions(None) == {}
        assert _sum_reactions([]) == {}

    def test_sum_reactions_basic(self):
        groups = [
            {"content": "THUMBS_UP", "users": {"totalCount": 5}},
            {"content": "HEART", "users": {"totalCount": 3}},
        ]
        result = _sum_reactions(groups)
        assert result == {"THUMBS_UP": 5, "HEART": 3}

    def test_sum_reactions_zero(self):
        groups = [{"content": "THUMBS_UP", "users": {"totalCount": 0}}]
        assert _sum_reactions(groups) == {}

    def test_render_reactions_bar(self):
        bar = _render_reactions_bar({"THUMBS_UP": 5, "HEART": 2})
        assert "👍 5" in bar
        assert "❤️ 2" in bar

    def test_render_reactions_bar_empty(self):
        assert _render_reactions_bar({}) == ""

    def test_render_issue_markdown_basic(self):
        data = {
            "title": "Fix the bug",
            "url": "https://github.com/astral-sh/uv/issues/1",
            "state": "OPEN",
            "createdAt": "2024-01-15T10:00:00Z",
            "author": {"login": "testuser"},
            "body": "This is a bug report.",
            "reactionGroups": [],
            "comments": [],
        }
        md = render_issue_markdown(data)
        assert "Fix the bug" in md
        assert "@testuser" in md
        assert "🚧 open" in md
        assert "No comments" in md

    def test_render_issue_markdown_with_reactions(self):
        data = {
            "title": "Feature request",
            "url": "https://github.com/owner/repo/issues/2",
            "state": "CLOSED",
            "createdAt": "2024-06-01T00:00:00Z",
            "author": {"login": "dev1"},
            "body": "Please add this feature.",
            "reactionGroups": [
                {"content": "THUMBS_UP", "users": {"totalCount": 42}},
                {"content": "HEART", "users": {"totalCount": 7}},
            ],
            "comments": [],
        }
        md = render_issue_markdown(data)
        assert "Feature request" in md
        assert "✅ closed" in md
        assert "👍 42" in md
        assert "❤️ 7" in md

    def test_render_issue_markdown_with_comments(self):
        data = {
            "title": "Discussion thread",
            "url": "https://github.com/owner/repo/issues/3",
            "state": "OPEN",
            "createdAt": "2024-01-01T00:00:00Z",
            "author": {"login": "opener"},
            "body": "Let's discuss.",
            "reactionGroups": [],
            "comments": [
                {
                    "author": {"login": "member1"},
                    "authorAssociation": "MEMBER",
                    "body": "I think we should do X.",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "url": "https://github.com/owner/repo/issues/3#issuecomment-1",
                    "reactionGroups": [{"content": "THUMBS_UP", "users": {"totalCount": 10}}],
                    "isMinimized": False,
                },
                {
                    "author": {"login": "contributor1"},
                    "authorAssociation": "CONTRIBUTOR",
                    "body": "Good idea!",
                    "createdAt": "2024-01-03T00:00:00Z",
                    "url": "https://github.com/owner/repo/issues/3#issuecomment-2",
                    "reactionGroups": [],
                    "isMinimized": False,
                },
                {
                    "author": {"login": "spammer"},
                    "authorAssociation": "NONE",
                    "body": "Spam message",
                    "createdAt": "2024-01-04T00:00:00Z",
                    "url": "https://github.com/owner/repo/issues/3#issuecomment-3",
                    "reactionGroups": [],
                    "isMinimized": True,
                },
            ],
        }
        md = render_issue_markdown(data)
        assert "I think we should do X." in md
        assert "Good idea!" in md
        assert "Spam message" not in md
        assert "🏷️" in md
        assert "@member1" in md
        assert "@contributor1" in md

    def test_render_issue_markdown_merged_pr(self):
        data = {
            "title": "Merge the feature",
            "url": "https://github.com/owner/repo/pull/42",
            "state": "MERGED",
            "createdAt": "2024-03-01T00:00:00Z",
            "author": {"login": "dev42"},
            "body": "This is the PR body.",
            "reactionGroups": [],
            "comments": [],
            "merged": True,
        }
        md = render_issue_markdown(data, kind="pr")
        assert "# Pull Request" in md
        assert "Merge the feature" in md
        assert "merged" in md
        assert "@dev42" in md
        assert "No comments" in md

    @patch("web_search_mcp.github.subprocess.run")
    def test_gh_available_true(self, mock_run):
        mock_run.return_value.returncode = 0
        from web_search_mcp.github import _gh_available

        assert _gh_available() is True

    @patch("web_search_mcp.github.subprocess.run")
    def test_gh_available_false(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        from web_search_mcp.github import _gh_available

        assert _gh_available() is False

    @patch("web_search_mcp.github.subprocess.run")
    def test_gh_authenticated_true(self, mock_run):
        mock_run.return_value.returncode = 0
        from web_search_mcp.github import _gh_authenticated

        assert _gh_authenticated() is True

    @patch("web_search_mcp.github.subprocess.run")
    def test_gh_authenticated_false(self, mock_run):
        mock_run.return_value.returncode = 1
        from web_search_mcp.github import _gh_authenticated

        assert _gh_authenticated() is False

    @patch("web_search_mcp.github._gh_available")
    @patch("web_search_mcp.github._gh_authenticated")
    @patch("web_search_mcp.github.subprocess.run")
    def test_get_github_issue_success(self, mock_run, mock_auth, mock_avail):
        mock_avail.return_value = True
        mock_auth.return_value = True
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "title": "Test Issue",
                "url": "https://github.com/owner/repo/issues/1",
                "state": "OPEN",
                "createdAt": "2024-06-01T00:00:00Z",
                "author": {"login": "user1"},
                "body": "Body text",
                "reactionGroups": [],
                "comments": [
                    {
                        "author": {"login": "user2"},
                        "authorAssociation": "NONE",
                        "body": "A comment",
                        "createdAt": "2024-06-02T00:00:00Z",
                        "url": "https://github.com/owner/repo/issues/1#issuecomment-1",
                        "reactionGroups": [],
                        "isMinimized": False,
                    }
                ],
            }
        )

        result = get_github_issue("https://github.com/owner/repo/issues/1")
        assert "Test Issue" in result
        assert "Body text" in result
        assert "A comment" in result
        assert "@user1" in result
        assert "@user2" in result

    @patch("web_search_mcp.github._gh_available")
    def test_get_github_issue_gh_not_installed(self, mock_avail):
        mock_avail.return_value = False
        result = get_github_issue("https://github.com/owner/repo/issues/1")
        assert "`gh` CLI is not installed" in result

    @patch("web_search_mcp.github._gh_available")
    @patch("web_search_mcp.github._gh_authenticated")
    def test_get_github_issue_gh_not_authed(self, mock_auth, mock_avail):
        mock_avail.return_value = True
        mock_auth.return_value = False
        result = get_github_issue("https://github.com/owner/repo/issues/1")
        assert "`gh` CLI is not authenticated" in result

    def test_get_github_issue_bad_url(self):
        result = get_github_issue("https://github.com/owner/repo")
        assert "URL is not a recognized" in result

    @patch("web_search_mcp.github._gh_available")
    @patch("web_search_mcp.github._gh_authenticated")
    @patch("web_search_mcp.github.subprocess.run")
    def test_get_github_issue_timeout(self, mock_run, mock_auth, mock_avail):
        mock_avail.return_value = True
        mock_auth.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = get_github_issue("https://github.com/owner/repo/issues/1")
        assert "timed out" in result

    @patch("web_search_mcp.github._gh_available")
    @patch("web_search_mcp.github._gh_authenticated")
    @patch("web_search_mcp.github.subprocess.run")
    @patch.dict("os.environ", {"GITHUB_ISSUE_MAX_CHARS": "5"})
    def test_get_github_issue_truncation(self, mock_run, mock_auth, mock_avail):
        mock_avail.return_value = True
        mock_auth.return_value = True
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(
            {
                "title": "Long issue",
                "url": "https://github.com/owner/repo/issues/1",
                "state": "OPEN",
                "createdAt": "2024-06-01T00:00:00Z",
                "author": {"login": "user1"},
                "body": "Some body text here",
                "reactionGroups": [],
                "comments": [],
            }
        )

        result = get_github_issue("https://github.com/owner/repo/issues/1")
        assert "_Truncated._" in result


if __name__ == "__main__":
    unittest.main()
