"""Offline unit tests for Digg search internals."""

from __future__ import annotations

from datetime import UTC, datetime

from web_search_mcp.tools.digg import (
    _parse_first_post_age,
    _parse_post,
    _rank_score,
    parse_digg_response,
)


class TestParseFirstPostAge:
    """Test relative age parsing with injectable clock."""

    def test_days(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age("5d", today) == "2024-07-10"
        assert _parse_first_post_age("17d", today) == "2024-06-28"

    def test_hours(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age("5h", today) == "2024-07-15"
        assert _parse_first_post_age("1h", today) == "2024-07-15"

    def test_weeks(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age("1w", today) == "2024-07-08"
        assert _parse_first_post_age("2w", today) == "2024-07-01"

    def test_months(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age("1m", today) == "2024-06-15"
        # 2m = 60 days > 30 day window -> None
        assert _parse_first_post_age("2m", today) is None

    def test_out_of_window_returns_none(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age("31d", today) is None
        assert _parse_first_post_age("40d", today) is None
        assert _parse_first_post_age("5w", today) is None

    def test_invalid_input_returns_none(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        assert _parse_first_post_age(None, today) is None
        assert _parse_first_post_age("", today) is None
        assert _parse_first_post_age("garbage", today) is None
        assert _parse_first_post_age("5x", today) is None
        assert _parse_first_post_age("-5d", today) is None
        assert _parse_first_post_age("d", today) is None


class TestRankScore:
    """Test Digg rank to score conversion."""

    def test_top_ranks(self) -> None:
        assert _rank_score(1) == 50.0
        assert _rank_score(25) == 26.0
        assert _rank_score(50) == 1.0

    def test_out_of_range_returns_zero(self) -> None:
        assert _rank_score(0) == 0.0
        assert _rank_score(51) == 0.0
        assert _rank_score(100) == 0.0

    def test_none_and_garbage_return_zero(self) -> None:
        assert _rank_score(None) == 0.0
        assert _rank_score("bad") == 0.0  # type: ignore[arg-type]
        assert _rank_score(-1) == 0.0


class TestParseDiggResponse:
    """Test the Digg response parser."""

    def test_parses_valid_cluster(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        response = {
            "results": [
                {
                    "clusterUrlId": "abc123",
                    "title": "Test Cluster",
                    "tldr": "TLDR text",
                    "rank": 5,
                    "postCount": 10,
                    "uniqueAuthors": 3,
                    "firstPostAge": "5d",
                }
            ]
        }
        items = parse_digg_response(response, "test", today=today)
        assert len(items) == 1
        item = items[0]
        assert item["id"] == "abc123"
        assert item["title"] == "Test Cluster"
        assert item["tldr"] == "TLDR text"
        assert item["date"] == "2024-07-10"
        assert item["engagement"]["postCount"] == 10
        assert item["engagement"]["uniqueAuthors"] == 3
        assert item["engagement"]["rank"] == 5
        assert item["engagement"]["rank_score"] == 46.0
        assert 0 <= item["relevance"] <= 1
        assert "posts" in item
        assert item["posts"] == []

    def test_drops_out_of_window_cluster(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        response = {
            "results": [
                {
                    "clusterUrlId": "abc123",
                    "title": "Test Cluster",
                    "firstPostAge": "5d",
                },
                {
                    "clusterUrlId": "def456",
                    "title": "Old Cluster",
                    "firstPostAge": "40d",  # >30 days -> dropped
                },
            ]
        }
        items = parse_digg_response(response, "test", today=today)
        assert len(items) == 1
        assert items[0]["id"] == "abc123"

    def test_handles_missing_optional_fields(self) -> None:
        today = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
        response = {"results": [{"clusterUrlId": "abc123", "title": "Minimal"}]}
        items = parse_digg_response(response, "test", today=today)
        assert len(items) == 1
        item = items[0]
        assert item["title"] == "Minimal"
        assert item["tldr"] == ""
        assert item["engagement"]["postCount"] == 0
        assert item["engagement"]["uniqueAuthors"] == 0
        assert item["engagement"]["rank"] is None
        assert item["engagement"]["rank_score"] == 0.0

    def test_empty_envelope_returns_empty(self) -> None:
        items = parse_digg_response({}, "test")
        assert items == []
        items = parse_digg_response({"results": []}, "test")
        assert items == []

    def test_non_list_results_returns_empty(self) -> None:
        items = parse_digg_response({"results": "not a list"}, "test")
        assert items == []


class TestParsePost:
    """Test the post parser for cluster X posts."""

    def test_valid_post(self) -> None:
        raw = {
            "body": "This is a tweet body",
            "author": {"username": "testuser", "display_name": "Test User", "category": "AI"},
            "xUrl": "https://x.com/testuser/status/123",
            "post_type": "tweet",
            "posted_at": "2024-07-15T12:00:00Z",
        }
        parsed = _parse_post(raw)
        assert parsed is not None
        assert parsed["username"] == "testuser"
        assert parsed["display_name"] == "Test User"
        assert parsed["category"] == "AI"
        assert parsed["body"] == "This is a tweet body"
        assert parsed["post_type"] == "tweet"
        assert parsed["x_url"] == "https://x.com/testuser/status/123"
        assert parsed["posted_at"] == "2024-07-15T12:00:00Z"

    def test_missing_body_returns_none(self) -> None:
        raw = {"author": {"username": "u"}, "xUrl": "https://x.com/u/status/1"}
        assert _parse_post(raw) is None

    def test_missing_username_returns_none(self) -> None:
        raw = {"body": "text", "author": {}, "xUrl": "https://x.com/u/status/1"}
        assert _parse_post(raw) is None

    def test_missing_xurl_returns_none(self) -> None:
        raw = {"body": "text", "author": {"username": "u"}}
        assert _parse_post(raw) is None

    def test_non_http_xurl_rejected(self) -> None:
        raw = {"body": "text", "author": {"username": "u"}, "xUrl": "javascript:alert(1)"}
        assert _parse_post(raw) is None

    def test_non_dict_input_returns_none(self) -> None:
        assert _parse_post("not a dict") is None  # type: ignore[arg-type]
        assert _parse_post(None) is None  # type: ignore[arg-type]
        assert _parse_post([1, 2, 3]) is None  # type: ignore[arg-type]
