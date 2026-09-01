"""Offline unit tests for formatting utilities."""
from __future__ import annotations

from web_search_mcp._utils.formatting import (
    assign_ids,
    date_to_unix,
    format_results_markdown,
    identify_url_dupes,
    iso_to_date,
    iso_to_epoch,
    iso_utc_to_date,
    truncate_content,
    unix_to_date,
)
from web_search_mcp._utils.scoring import token_overlap_relevance


class TestTruncateContent:
    """Test truncate_content with environment variable control."""

    def test_truncates_when_longer_than_limit(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TRUNCATE_LIMIT", "5")
        text = "hello world"
        result = truncate_content(text, "TEST_TRUNCATE_LIMIT")
        assert result == "hello\n\n_Truncated._\n"

    def test_fallback_to_default_when_unparsable(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TRUNCATE_BAD", "not-a-number")
        text = "x" * 30001
        result = truncate_content(text, "TEST_TRUNCATE_BAD")
        assert "_Truncated._" in result
        assert len(result) <= 30000 + len("\n\n_Truncated._\n")

    def test_no_change_when_under_limit(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TRUNCATE_SPACIOUS", "10000")
        text = "short"
        result = truncate_content(text, "TEST_TRUNCATE_SPACIOUS")
        assert result == "short"

    def test_no_change_when_max_chars_zero(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TRUNCATE_ZERO", "0")
        text = "anything"
        result = truncate_content(text, "TEST_TRUNCATE_ZERO")
        assert result == "anything"

    def test_custom_default_used_when_var_missing(self) -> None:
        text = "hello world"
        result = truncate_content(text, "NONEXISTENT_VAR_12345", default=3)
        assert result == "hel\n\n_Truncated._\n"

    def test_no_truncation_exact_match(self, monkeypatch: object) -> None:
        monkeypatch.setenv("TEST_TRUNCATE_EXACT", "5")
        text = "hello"
        result = truncate_content(text, "TEST_TRUNCATE_EXACT")
        assert result == "hello"


class TestFormatResultsMarkdown:
    """Test format_results_markdown for empty/with items."""

    def test_empty_items_returns_no_results_message(self) -> None:
        result = format_results_markdown([], "query", "Platform")
        assert result == "No Platform results found for 'query'."

    def test_no_format_item_produces_title_only(self) -> None:
        items = [{"title": "T1", "url": "https://example.com/1"}]
        result = format_results_markdown(items, "q", "Platform")
        assert "# Platform Results for 'q'" in result
        assert "Found 1 results." in result
        assert "T1" not in result

    def test_with_format_item_includes_custom_lines(self) -> None:
        items = [{"title": "T1", "url": "https://example.com/1"}]

        def fmt(item: dict, idx: int) -> list[str]:
            return [f"  {idx}. {item.get('title')}"]

        result = format_results_markdown(items, "q", "Platform", format_item=fmt)
        assert "  1. T1" in result


class TestDateHelpers:
    """Test iso_to_date, iso_to_epoch, date_to_unix, unix_to_date, iso_utc_to_date."""

    def test_iso_to_date_valid(self) -> None:
        assert iso_to_date("2024-06-15T10:30:00Z") == "2024-06-15"
        assert iso_to_date("2024-01-01T00:00:00+05:00") == "2024-01-01"

    def test_iso_to_date_none(self) -> None:
        assert iso_to_date(None) is None
        assert iso_to_date("") is None

    def test_iso_to_date_invalid(self) -> None:
        assert iso_to_date("not-a-date") is None
        assert iso_to_date("2024-13-01") is None

    def test_iso_to_epoch_valid(self) -> None:
        result = iso_to_epoch("2024-01-01T00:00:00Z")
        assert result == 1704067200.0

    def test_iso_to_epoch_none(self) -> None:
        assert iso_to_epoch(None) is None
        assert iso_to_epoch("") is None

    def test_iso_to_epoch_invalid(self) -> None:
        assert iso_to_epoch("garbage") is None

    def test_date_to_unix(self) -> None:
        assert date_to_unix("2024-01-01") == 1704067200

    def test_unix_to_date(self) -> None:
        assert unix_to_date(1704067200) == "2024-01-01"

    def test_iso_utc_to_date_valid(self) -> None:
        assert iso_utc_to_date(1704067200.0) == "2024-01-01"

    def test_iso_utc_to_date_none_falsy(self) -> None:
        assert iso_utc_to_date(0) is None
        assert iso_utc_to_date(None) is None


class TestIdentifyUrlDupes:
    """Test deduplication by key, keeping first occurrence."""

    def test_deduplication_keeps_first(self) -> None:
        items = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://b.com", "title": "B"},
            {"url": "https://a.com", "title": "A-dup"},
        ]
        result = identify_url_dupes(items)
        assert len(result) == 2
        assert result[0]["title"] == "A"
        assert result[1]["title"] == "B"

    def test_skips_empty_keys(self) -> None:
        items = [
            {"url": "", "title": "empty"},
            {"url": "https://x.com", "title": "x"},
            {"url": "", "title": "empty2"},
        ]
        result = identify_url_dupes(items)
        assert len(result) == 1
        assert result[0]["title"] == "x"

    def test_custom_key(self) -> None:
        items = [
            {"slug": "a", "title": "A"},
            {"slug": "b", "title": "B"},
            {"slug": "a", "title": "A2"},
        ]
        result = identify_url_dupes(items, key="slug")
        assert len(result) == 2


class TestAssignIds:
    """Test sequential ID assignment."""

    def test_assigns_sequential_ids(self) -> None:
        items = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        assign_ids(items, "RES")
        assert items[0]["id"] == "RES1"
        assert items[1]["id"] == "RES2"
        assert items[2]["id"] == "RES3"

    def test_empty_list_noop(self) -> None:
        assign_ids([], "X")


class TestTokenOverlapRelevance:
    """Test token overlap relevance edge cases."""

    def test_whitespace_only_text_returns_zero(self) -> None:
        result = token_overlap_relevance("hello", "   \t\n  ")
        assert result == 0.0

    def test_whitespace_only_query_returns_zero(self) -> None:
        result = token_overlap_relevance("   ", "hello world")
        assert result == 0.0

    def test_no_overlap_returns_zero(self) -> None:
        result = token_overlap_relevance("apple", "orange banana")
        assert result == 0.0

    def test_full_overlap_returns_one(self) -> None:
        result = token_overlap_relevance("hello world", "hello world")
        assert result == 1.0