"""Tests for X/Twitter search module."""

import os
import unittest
from unittest.mock import patch, MagicMock

from web_search_mcp.x import (
    is_available,
    is_authenticated,
    search_x,
    _safe_int,
    _parse_item,
)


class TestHelpers(unittest.TestCase):
    """Tests for helper functions."""

    def test_safe_int_with_int(self):
        assert _safe_int(42) == 42

    def test_safe_int_with_string(self):
        assert _safe_int("42") == 42

    def test_safe_int_with_none(self):
        assert _safe_int(None) is None

    def test_safe_int_with_invalid(self):
        assert _safe_int("not-a-number") is None

    def test_safe_int_with_zero(self):
        assert _safe_int(0) == 0

    def test_parse_item_no_url_returns_none(self):
        tweet = {"text": "hello world"}
        result = _parse_item(tweet, 0, "test")
        assert result is None

    def test_parse_item_with_url_and_text(self):
        tweet = {
            "text": "This is a tweet about Claude Code",
            "url": "https://x.com/user/status/12345",
            "author_handle": "testuser",
            "likeCount": 100,
            "retweetCount": 20,
        }
        result = _parse_item(tweet, 0, "Claude")
        assert result is not None
        assert result["id"] == "X1"
        assert result["url"] == "https://x.com/user/status/12345"
        assert result["author_handle"] == "testuser"
        assert result["engagement"]["likes"] == 100
        assert result["engagement"]["retweets"] == 20

    def test_parse_item_with_iso_date(self):
        tweet = {
            "text": "Tweet with ISO date",
            "url": "https://x.com/user/status/1",
            "createdAt": "2026-06-01T12:00:00Z",
        }
        result = _parse_item(tweet, 0, "test")
        assert result is not None
        assert result["date"] == "2026-06-01"

    def test_parse_item_with_twitter_date(self):
        tweet = {
            "text": "Tweet with Twitter format date",
            "url": "https://x.com/user/status/1",
            "created_at": "Mon Jun 1 12:00:00 +0000 2026",
        }
        result = _parse_item(tweet, 0, "test")
        assert result is not None
        assert result["date"] == "2026-06-01"

    def test_parse_item_constructs_url_from_id_and_author(self):
        tweet = {
            "text": "Tweet without url field",
            "id": "67890",
            "author": {"username": "dev_user"},
        }
        result = _parse_item(tweet, 0, "test")
        assert result is not None
        assert result["url"] == "https://x.com/dev_user/status/67890"

    def test_parse_item_non_dict_returns_none(self):
        assert _parse_item("not a dict", 0, "test") is None

    def test_parse_item_no_engagement(self):
        tweet = {
            "text": "Tweet without engagement data",
            "url": "https://x.com/user/status/1",
        }
        result = _parse_item(tweet, 0, "test")
        assert result is not None
        assert result["engagement"] == {}


class TestAvailability(unittest.TestCase):
    """Tests for availability checks."""

    @patch("web_search_mcp.x.shutil.which")
    @patch("web_search_mcp.x._BIRD_SEARCH_MJS")
    def test_is_available_true(self, mock_path, mock_which):
        mock_path.exists.return_value = True
        mock_which.return_value = "/usr/bin/node"
        assert is_available() is True

    @patch("web_search_mcp.x._BIRD_SEARCH_MJS")
    def test_is_available_no_bird_file(self, mock_path):
        mock_path.exists.return_value = False
        assert is_available() is False

    @patch("web_search_mcp.x.shutil.which")
    @patch("web_search_mcp.x._BIRD_SEARCH_MJS")
    def test_is_available_no_node(self, mock_path, mock_which):
        mock_path.exists.return_value = True
        mock_which.return_value = None
        assert is_available() is False

    def test_is_authenticated_true(self):
        with patch.dict(os.environ, {"AUTH_TOKEN": "abc123", "CT0": "xyz789"}, clear=False):
            assert is_authenticated() is True

    def test_is_authenticated_false_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_authenticated() is False

    def test_is_authenticated_false_only_token(self):
        with patch.dict(os.environ, {"AUTH_TOKEN": "abc123"}, clear=True):
            assert is_authenticated() is False


class TestSearchX(unittest.TestCase):
    """Tests for search_x main function."""

    @patch("web_search_mcp.x.is_authenticated")
    @patch("web_search_mcp.x.is_available")
    @patch("web_search_mcp.x.subprocess.run")
    def test_search_x_returns_parsed_items(self, mock_run, mock_avail, mock_auth):
        mock_avail.return_value = True
        mock_auth.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '[{"text": "Love Claude Code!", "url": "https://x.com/user/status/1",'
            '"author": {"username": "dev1"}, "likeCount": 50, "createdAt": "2026-06-01T10:00:00Z"}]'
        )
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        items = search_x("Claude Code", from_date="2026-05-01", depth="quick")
        assert len(items) == 1
        assert items[0]["text"] == "Love Claude Code!"
        assert items[0]["author_handle"] == "dev1"
        assert items[0]["date"] == "2026-06-01"

    @patch("web_search_mcp.x.is_authenticated")
    @patch("web_search_mcp.x.is_available")
    def test_search_x_not_available(self, mock_avail, mock_auth):
        mock_avail.return_value = False
        result = search_x("test")
        assert "error" in result[0]

    @patch("web_search_mcp.x.is_authenticated")
    @patch("web_search_mcp.x.is_available")
    def test_search_x_not_authenticated(self, mock_avail, mock_auth):
        mock_avail.return_value = True
        mock_auth.return_value = False
        result = search_x("test")
        assert "error" in result[0]

    @patch("web_search_mcp.x.is_authenticated")
    @patch("web_search_mcp.x.is_available")
    @patch("web_search_mcp.x.subprocess.run")
    def test_search_x_non_zero_exit(self, mock_run, mock_avail, mock_auth):
        mock_avail.return_value = True
        mock_auth.return_value = True
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Rate limited"
        mock_run.return_value = mock_result

        items = search_x("test")
        assert items == []

    @patch("web_search_mcp.x.is_authenticated")
    @patch("web_search_mcp.x.is_available")
    @patch("web_search_mcp.x.subprocess.run")
    def test_search_x_timeout(self, mock_run, mock_avail, mock_auth):
        mock_avail.return_value = True
        mock_auth.return_value = True
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("bird-search", timeout=30)

        items = search_x("test")
        assert items == []


if __name__ == "__main__":
    unittest.main()
