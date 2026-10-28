"""Offline unit tests for Hacker News helper functions."""

from __future__ import annotations

from web_search_mcp.social.hackernews import (
    _build_search_params,
    _extract_comments,
    _flatten_query,
    _normalize_search_hit,
    _normalize_search_hits,
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


class TestBuildSearchParams:
    """Test _build_search_params request-parameter construction."""

    def test_basic_params(self) -> None:
        params = _build_search_params("MCP server", count=25)
        assert params["query"] == "MCP server"
        assert params["tags"] == "story"
        assert params["hitsPerPage"] == "25"
        assert params["optionalWords"] == "server"
        assert "numericFilters" not in params

    def test_flattens_query(self) -> None:
        params = _build_search_params("hello-world, foo")
        assert params["query"] == "hello world foo"

    def test_single_token_no_optional_words(self) -> None:
        params = _build_search_params("solitary")
        assert "optionalWords" not in params

    def test_multi_token_optional_words(self) -> None:
        params = _build_search_params("foo bar baz")
        assert params["optionalWords"] == "bar baz"

    def test_date_window_adds_numeric_filters(self) -> None:
        params = _build_search_params("foo", "2024-01-01", "2024-01-31")
        assert "created_at_i>" in params["numericFilters"]
        assert "created_at_i<" in params["numericFilters"]
        assert "points>2" in params["numericFilters"]

    def test_one_sided_dates_no_numeric_filters(self) -> None:
        params = _build_search_params("foo", from_date="2024-01-01")
        assert "numericFilters" not in params


class TestNormalizeSearchHit:
    """Test _normalize_search_hit single-hit normalization."""

    def test_matches_query_returns_item(self) -> None:
        hit = {
            "objectID": "123",
            "title": "Ask HN: Rust vs Go",
            "url": "https://example.com",
            "points": 50,
            "num_comments": 7,
            "created_at_i": 1700000000,
            "author": "dev",
        }
        item = _normalize_search_hit(hit, "rust", rank=0)
        assert item is not None
        assert item["id"] == "123"
        assert item["title"] == "Ask HN: Rust vs Go"
        assert item["hn_url"] == "https://news.ycombinator.com/item?id=123"
        assert item["engagement"] == {"points": 50, "comments": 7}
        assert "relevance" in item
        assert item["why_relevant"] == "HN: Ask HN: Rust vs Go"

    def test_non_matching_title_returns_none(self) -> None:
        hit = {"objectID": "1", "title": "Completely unrelated", "points": 5}
        assert _normalize_search_hit(hit, "python", rank=0) is None

    def test_empty_query_keeps_all(self) -> None:
        hit = {"objectID": "9", "title": "Anything goes", "points": 1}
        assert _normalize_search_hit(hit, "", rank=3) is not None

    def test_missing_fields_default_safely(self) -> None:
        item = _normalize_search_hit({"objectID": "5"}, "", rank=0)
        assert item is not None
        assert item["title"] == ""
        assert item["url"] == ""
        assert item["engagement"] == {"points": 0, "comments": 0}
        assert item["date"] is None
        assert item["author"] == ""

    def test_created_at_i_converted_to_date(self) -> None:
        hit = {"objectID": "7", "title": "x", "created_at_i": 1700000000}
        item = _normalize_search_hit(hit, "x", rank=0)
        assert item is not None
        assert item["date"] is not None
        assert item["date"].count("-") == 2  # YYYY-MM-DD


class TestNormalizeSearchHits:
    """Test _normalize_search_hits batch filter + sort."""

    def test_empty_hits(self) -> None:
        assert _normalize_search_hits("q", []) == []

    def test_filters_non_matching(self) -> None:
        hits = [
            {"objectID": "1", "title": "Python tips", "points": 10},
            {"objectID": "2", "title": "Totally unrelated", "points": 99},
            {"objectID": "3", "title": "More Python", "points": 1},
        ]
        items = _normalize_search_hits("python", hits)
        assert len(items) == 2
        assert {i["id"] for i in items} == {"1", "3"}

    def test_sorted_by_relevance_desc(self) -> None:
        hits = [
            {"objectID": "a", "title": "low signal python", "points": 0},
            {"objectID": "b", "title": "python scripting boost rocks", "points": 1000},
        ]
        items = _normalize_search_hits("python scripting boost", hits)
        assert [i["id"] for i in items] == ["b", "a"]


class TestExtractComments:
    """Test _extract_comments reduction of raw story children."""

    def test_empty_children(self) -> None:
        result = _extract_comments([])
        assert result == {"comments": [], "comment_insights": []}

    def test_filters_out_missing_text_or_author(self) -> None:
        children = [
            {"text": "no author", "points": 100},
            {"author": "ghost", "points": 100},
            {"author": "real", "text": "real comment", "points": 5},
        ]
        result = _extract_comments(children)
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author"] == "real"

    def test_ranks_by_points_desc(self) -> None:
        children = [
            {"author": "a", "text": "low", "points": 1},
            {"author": "b", "text": "high", "points": 50},
            {"author": "c", "text": "mid", "points": 10},
        ]
        result = _extract_comments(children, max_comments=3)
        assert [c["points"] for c in result["comments"]] == [50, 10, 1]

    def test_respects_max_comments(self) -> None:
        children = [{"author": f"a{i}", "text": f"t{i}", "points": i} for i in range(10)]
        result = _extract_comments(children, max_comments=2)
        assert len(result["comments"]) == 2
        assert [c["points"] for c in result["comments"]] == [9, 8]

    def test_strips_html_and_truncates_excerpt(self) -> None:
        long_text = "<p>" + "word " * 200 + "</p>"  # >300 chars
        children = [{"author": "a", "text": long_text, "points": 1}]
        result = _extract_comments(children)
        excerpt = result["comments"][0]["text"]
        assert "<" not in excerpt
        assert excerpt.endswith("...")
        assert len(excerpt) == 303

    def test_builds_insight_from_first_sentence(self) -> None:
        children = [
            {"author": "a", "text": "First insight here. Second sentence.", "points": 1},
        ]
        result = _extract_comments(children)
        assert result["comment_insights"] == ["First insight here"]

    def test_no_insight_when_no_sentences(self) -> None:
        children = [{"author": "a", "text": "no punctuation at all", "points": 1}]
        # first sentence splits on ". " and newline; whole text kept
        result = _extract_comments(children)
        assert result["comment_insights"] == ["no punctuation at all"]
