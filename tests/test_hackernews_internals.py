"""Offline unit tests for Hacker News helper functions."""

from __future__ import annotations

from web_search_mcp.social.hackernews import (
    _flatten_query,
    _strip_html,
    _title_matches_query,
    format_hackernews_markdown,
)


class TestStripHtml:
    """Test HTML tag stripping and entity decoding."""

    def test_strips_tags(self) -> None:
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self) -> None:
        assert "&" in _strip_html("Tom &amp; Jerry")
        assert "<" in _strip_html("5 &lt; 10")
        assert ">" in _strip_html("10 &gt; 5")

    def test_strips_p_tags_converts_to_newline(self) -> None:
        result = _strip_html("<p>line1</p><p>line2</p>")
        assert "\n" in result

    def test_leaves_plain_text_untouched(self) -> None:
        assert _strip_html("just text") == "just text"

    def test_strips_empty_tags(self) -> None:
        assert _strip_html("<br><p>hello</p>") == "hello"

    def test_strips_self_closing_tags(self) -> None:
        result = _strip_html("<p>text<br/></p>")
        assert result == "text"

    def test_strips_attributes(self) -> None:
        assert _strip_html('<a href="http://x.com">link</a>') == "link"


class TestFlattenQuery:
    """Test query normalisation: hyphens and commas to spaces."""

    def test_hyphens_to_spaces(self) -> None:
        assert _flatten_query("foo-bar") == "foo bar"

    def test_commas_to_spaces(self) -> None:
        assert _flatten_query("foo,bar") == "foo bar"

    def test_multiple_separators(self) -> None:
        assert _flatten_query("a,b-c") == "a b c"

    def test_already_clean_unchanged(self) -> None:
        assert _flatten_query("hello world") == "hello world"

    def test_extra_whitespace_collapsed(self) -> None:
        assert _flatten_query("hello   world") == "hello world"


class TestTitleMatchesQuery:
    """Test title matching with query tokens."""

    def test_empty_query_matches_all(self) -> None:
        assert _title_matches_query("Some Title", "") is True
        assert _title_matches_query("Any Title", "  ") is True

    def test_no_match_returns_false(self) -> None:
        assert _title_matches_query("Hello world", "xyz") is False

    def test_prefix_match_returns_true(self) -> None:
        assert _title_matches_query("Hello world", "hello") is True

    def test_show_hn_prefix_stripped_before_match(self) -> None:
        """Titles with 'Show HN:' prefix should still match the query against the rest."""
        assert _title_matches_query("Show HN: my project", "project") is True
        assert _title_matches_query("Tell HN: idea", "idea") is True
        assert _title_matches_query("Ask HN: help", "help") is True

    def test_query_with_hyphen_flattened(self) -> None:
        assert _title_matches_query("python asyncio tutorial", "python-asyncio") is True


class TestFormatHackernewsMarkdown:
    """Test format_hackernews_markdown output."""

    def test_empty_items_returns_no_results(self) -> None:
        result = format_hackernews_markdown([], "query")
        assert "No Hacker News results found for 'query'" in result

    def test_items_rendered_with_points_and_comments(self) -> None:
        items = [
            {
                "title": "Test Story",
                "url": "https://hn.example.com/1",
                "engagement": {"points": 10, "comments": 3},
                "date": "2024-01-01",
            }
        ]
        result = format_hackernews_markdown(items, "test")
        assert "# Hacker News Results for 'test'" in result
        assert "Test Story" in result
        assert "10 points, 3 comments" in result
        assert "2024-01-01" in result

    def test_items_with_top_comments_includes_them(self) -> None:
        items = [
            {
                "title": "Story",
                "url": "https://hn.example.com/1",
                "engagement": {"points": 5, "comments": 1},
                "date": "",
                "top_comments": [
                    {"text": "Great post!"},
                    {"text": "I disagree."},
                ],
            }
        ]
        result = format_hackernews_markdown(items, "q")
        assert "Top comments:" in result
        assert "> Great post!" in result
        assert "> I disagree." in result

    def test_missing_engagement_defaults_to_zero(self) -> None:
        items = [{"title": "No engagement", "url": "https://hn.example.com/2"}]
        result = format_hackernews_markdown(items, "q")
        assert "0 points, 0 comments" in result
