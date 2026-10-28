"""Offline unit tests for Techmeme search internals."""

from __future__ import annotations

from web_search_mcp.tools.techmeme import (
    _is_story_headline,
    _record_iso_date,
    parse_techmeme_response,
    window_records,
)


class TestWindowRecords:
    """Test the pure date-windowing function."""

    def test_keeps_dated_in_window_first(self) -> None:
        records = [
            {"date": "2024-06-15", "title": "A"},
            {"date": "2024-07-15", "title": "B"},
            {"title": "C"},  # undated
        ]
        kept, dropped = window_records(records, "2024-07-01", "2024-07-31", 10)
        assert [r["title"] for r in kept] == ["B", "C"]
        assert dropped == 1

    def test_drops_dated_out_of_window(self) -> None:
        records = [
            {"date": "2024-06-15", "title": "old"},
            {"date": "2024-08-15", "title": "future"},
        ]
        kept, dropped = window_records(records, "2024-07-01", "2024-07-31", 10)
        assert kept == []
        assert dropped == 2

    def test_undated_kept_after_dated(self) -> None:
        records = [
            {"title": "undated1"},
            {"date": "2024-07-15", "title": "dated"},
            {"title": "undated2"},
        ]
        kept, dropped = window_records(records, "2024-07-01", "2024-07-31", 10)
        assert [r["title"] for r in kept] == ["dated", "undated1", "undated2"]
        assert dropped == 0

    def test_respects_limit_cap(self) -> None:
        records = [
            {"date": "2024-07-10", "title": "1"},
            {"date": "2024-07-11", "title": "2"},
            {"date": "2024-07-12", "title": "3"},
        ]
        kept, dropped = window_records(records, "2024-07-01", "2024-07-31", 2)
        assert len(kept) == 2
        assert [r["title"] for r in kept] == ["1", "2"]
        assert dropped == 0

    def test_empty_input(self) -> None:
        kept, dropped = window_records([], "2024-01-01", "2024-12-31", 10)
        assert kept == []
        assert dropped == 0


class TestRecordIsoDate:
    """Test the ISO date extraction helper."""

    def test_valid_iso_date(self) -> None:
        assert _record_iso_date({"date": "2024-07-15"}) == "2024-07-15"

    def test_none_when_missing(self) -> None:
        assert _record_iso_date({"title": "no date"}) is None

    def test_none_when_invalid_format(self) -> None:
        assert _record_iso_date({"date": "not-a-date"}) is None

    def test_none_when_not_string(self) -> None:
        assert _record_iso_date({"date": 123}) is None


class TestIsStoryHeadline:
    """Test the headline validation filter."""

    def test_valid_headline(self) -> None:
        assert _is_story_headline("Apple announces new iPhone", "Apple") is True

    def test_too_few_words(self) -> None:
        assert _is_story_headline("Hi", "source") is False
        assert _is_story_headline("One two three", "source") is False

    def test_headline_equals_source_rejected(self) -> None:
        assert _is_story_headline("TechCrunch", "TechCrunch") is False

    def test_empty_headline_rejected(self) -> None:
        assert _is_story_headline("", "source") is False


class TestParseTechmemeResponse:
    """Test the response parser."""

    def test_parses_valid_records(self) -> None:
        response = {
            "results": [
                {
                    "headline": "Apple announces new iPhone today",
                    "source": "TechCrunch",
                    "link": "https://example.com/1",
                    "date": "2024-07-15",
                },
                {
                    "headline": "Google releases Android 15 beta now",
                    "source": "The Verge",
                    "link": "https://example.com/2",
                    "date": "2024-07-14",
                },
            ]
        }
        items = parse_techmeme_response(response, "apple")
        assert len(items) == 2
        assert items[0]["title"] == "Apple announces new iPhone today"
        assert items[0]["url"] == "https://example.com/1"
        assert items[0]["source_name"] == "TechCrunch"
        assert items[0]["date"] == "2024-07-15"
        assert 0 <= items[0]["relevance"] <= 1

    def test_scores_by_relevance_not_filter(self) -> None:
        response = {
            "results": [
                {
                    "headline": "Apple news breaks today worldwide",
                    "source": "A",
                    "link": "https://a.com",
                    "date": "2024-07-15",
                },
                {
                    "headline": "Microsoft news updates just now",
                    "source": "B",
                    "link": "https://b.com",
                    "date": "2024-07-15",
                },
            ]
        }
        items = parse_techmeme_response(response, "apple")
        # Both items included; Apple one scored higher
        assert len(items) == 2
        assert items[0]["title"] == "Apple news breaks today worldwide"
        assert items[0]["relevance"] > items[1]["relevance"]

    def test_drops_records_without_link(self) -> None:
        response = {
            "results": [
                {
                    "headline": "Valid headline with enough words",
                    "source": "A",
                    "link": "https://a.com",
                    "date": "2024-07-15",
                },
                {"headline": "No link here at all", "source": "B", "date": "2024-07-15"},
            ]
        }
        items = parse_techmeme_response(response, "test")
        assert len(items) == 1
        assert items[0]["title"] == "Valid headline with enough words"

    def test_relevance_bounded(self) -> None:
        response = {
            "results": [
                {
                    "headline": "Apple announces new iPhone today with many features and updates and more",
                    "source": "S",
                    "link": "https://x.com",
                    "date": "2024-07-15",
                },
            ]
        }
        items = parse_techmeme_response(response, "query")
        assert len(items) == 1
        assert 0 <= items[0]["relevance"] <= 1
