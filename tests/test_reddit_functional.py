"""Functional tests for Reddit search MCP tools.

Tests the full call chain from the MCP tool interface through to the
core logic in the reddit module, mocking only external network services.

Structure:
  - MCP tool layer: tests exercise the FastMCP in-memory client
  - reddit/__init__.py edge cases: uncovered branches
  - reddit/parsers.py edge cases: uncovered parsing branches
  - reddit/engine.py edge cases: uncovered logic branches
  - reddit/client.py edge cases: retry and error handling
  - reddit/models.py edge cases: listing parsing
"""

from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
import tenacity
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from web_search_mcp.reddit import (
    reddit_search_tool,
    reddit_rss_search,
    _convert_to_search_results,
)
from web_search_mcp.reddit import parsers
from web_search_mcp.reddit import client as reddit_client
from web_search_mcp.reddit import engine
from web_search_mcp.reddit import models as listing_models
from web_search_mcp.reddit.client import HTTPError, _should_retry_http, _is_dns_failure
from web_search_mcp.models import SearchResponse, ErrorResponse
from web_search_mcp.server import mcp

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """In-memory FastMCP client backed by the real server instance."""
    transport = FastMCPTransport(mcp)
    async with Client(transport) as c:
        yield c


# ============================================================================
# MCP Tool Layer — reddit_search
# ============================================================================


class TestRedditSearchTool:
    """Functional tests for the reddit_search MCP tool through FastMCP."""

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._reddit_search_tool")
    async def test_reddit_search_basic(self, mock_fn, client):
        """Basic reddit_search call returns markdown by default."""
        mock_fn.return_value = "# Reddit Search Results for 'test'\nFound 1 posts.\n\n1. **[Post](https://r/1)**\n   r/python • 50 upvotes • 10 comments\n"
        result = await client.call_tool("reddit_search", {"query": "python async"})
        assert "Reddit Search Results" in result.data
        mock_fn.assert_called_once_with(
            query="python async",
            search_type="text",
            max_results=25,
            time_range=None,
            depth="default",
            subreddits=None,
            response_format="markdown",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._reddit_search_tool")
    async def test_reddit_search_all_params(self, mock_fn, client):
        """All parameters forwarded correctly."""
        mock_fn.return_value = "markdown output"
        await client.call_tool(
            "reddit_search",
            {
                "query": "test query",
                "search_type": "text",
                "max_results": 10,
                "time_range": "w",
                "depth": "deep",
                "subreddits": ["Python", "learnpython"],
                "response_format": "json",
            },
        )
        mock_fn.assert_called_once_with(
            query="test query",
            search_type="text",
            max_results=10,
            time_range="w",
            depth="deep",
            subreddits=["Python", "learnpython"],
            response_format="json",
        )

    @pytest.mark.asyncio
    @patch("web_search_mcp.server._reddit_search_tool")
    async def test_reddit_search_error_response(self, mock_fn, client):
        """ErrorResponse from reddit_search_tool is passed through."""
        mock_fn.return_value = ErrorResponse(error="Reddit search failed", details="Timeout")
        result = await client.call_tool("reddit_search", {"query": "test"})
        assert isinstance(result.data, dict)
        assert "Reddit search failed" in str(result.data)


# ============================================================================
# reddit/__init__.py — reddit_search_tool edge cases
# ============================================================================


class TestRedditSearchToolUnit:
    """Edge cases in reddit_search_tool not yet covered."""

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_markdown_format_with_full_post(self, mock_search):
        """Markdown format renders all post fields."""
        mock_search.return_value = [
            {
                "title": "Full Post",
                "url": "https://reddit.com/r/test/comments/abc",
                "subreddit": "test",
                "score": 150,
                "num_comments": 30,
                "selftext": "This is a longer selftext for testing purposes that should be truncated to 200 chars in the markdown output.",
                "top_comments": [
                    {
                        "excerpt": "Top level comment with interesting take",
                        "score": 42,
                        "author": "user1",
                    },
                    {"excerpt": "Second comment", "score": 10, "author": "user2"},
                ],
            },
            {
                "title": "Minimal Post",
                "url": "https://reddit.com/r/test/comments/def",
                "subreddit": "test",
                "score": 5,
                "num_comments": 1,
                "selftext": "",
                "top_comments": [],
            },
        ]
        result = reddit_search_tool("test query", response_format="markdown")
        assert isinstance(result, str)
        assert "Full Post" in result
        assert "150 upvotes" in result
        assert "30 comments" in result
        assert "Top comment: Top level comment" in result
        assert "Minimal Post" in result
        assert "5 upvotes" in result

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_json_format_converts_post_structure(self, mock_search):
        """JSON format converts enriched post dicts to SearchResponse."""
        mock_search.return_value = [
            {
                "title": "JSON Post",
                "url": "https://reddit.com/r/test/comments/xyz",
                "subreddit": "test",
                "score": 75,
                "num_comments": 12,
                "selftext": "Selftext content here",
                "top_comments": [
                    {"excerpt": "A comment excerpt", "score": 20, "author": "user3"},
                ],
            }
        ]
        result = reddit_search_tool("test query", response_format="json")
        assert isinstance(result, SearchResponse)
        assert result.query == "test query"
        assert len(result.results) == 1
        assert result.results[0].title == "JSON Post"
        assert result.results[0].href == "https://reddit.com/r/test/comments/xyz"
        assert "Selftext" in result.results[0].body
        assert "A comment excerpt" in result.results[0].body

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_json_format_handles_missing_fields(self, mock_search):
        """Post without title/url/selftext/comments still converts cleanly."""
        mock_search.return_value = [
            {
                "title": "",
                "url": "",
                "subreddit": "",
                "score": 0,
                "num_comments": 0,
                "top_comments": None,
            }
        ]
        result = reddit_search_tool("test", response_format="json")
        assert isinstance(result, SearchResponse)
        assert result.total_results == 1
        # title defaults to "" since the dict has key "title" with value ""
        # (dict.get won't trigger the default)
        assert result.results[0].title == ""
        assert result.results[0].body is None

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_time_range_maps_all_values(self, mock_search):
        """All time_range values map to relative dates."""
        mock_search.return_value = []
        today = datetime.now().date()

        reddit_search_tool("test", time_range="d", response_format="markdown")
        from_date = mock_search.call_args.kwargs["from_date"]
        assert from_date == (today - timedelta(days=1)).isoformat()

        mock_search.reset_mock()
        reddit_search_tool("test", time_range="w", response_format="markdown")
        from_date_w = mock_search.call_args.kwargs["from_date"]
        assert from_date_w == (today - timedelta(weeks=1)).isoformat()

        mock_search.reset_mock()
        reddit_search_tool("test", time_range="m", response_format="markdown")
        from_date_m = mock_search.call_args.kwargs["from_date"]
        assert from_date_m == (today - timedelta(weeks=4)).isoformat()

        mock_search.reset_mock()
        reddit_search_tool("test", time_range="y", response_format="markdown")
        from_date_y = mock_search.call_args.kwargs["from_date"]
        assert from_date_y == (today - timedelta(weeks=52)).isoformat()

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_depths_cap_max_results(self, mock_search):
        """Depth parameter caps max_results: quick=10, default=25, deep=50."""
        mock_search.return_value = []
        reddit_search_tool("test", max_results=100, depth="quick", response_format="markdown")
        args_quick = mock_search.call_args.kwargs
        assert args_quick["depth"] == "quick"

        mock_search.reset_mock()
        reddit_search_tool("test", max_results=100, depth="deep", response_format="markdown")
        args_deep = mock_search.call_args.kwargs
        assert args_deep["depth"] == "deep"

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_search_exception_handling(self, mock_search):
        """Exception in search_and_enrich returns ErrorResponse."""
        mock_search.side_effect = RuntimeError("reddit failure")
        result = reddit_search_tool("test", response_format="markdown")
        assert isinstance(result, ErrorResponse)
        assert "Reddit search failed" in result.error


# ============================================================================
# reddit/__init__.py — _convert_to_search_results
# ============================================================================


class TestConvertToSearchResults:
    """Edge cases for the post-to-SearchResponse converter."""

    def test_post_with_all_fields(self):
        """Post with title, selftext, and top_comments."""
        posts = [
            {
                "title": "Test Title",
                "url": "https://r/test/1",
                "selftext": "A" * 500,  # longer than 300 limit
                "top_comments": [
                    {"excerpt": "C1"},
                    {"excerpt": "C2"},
                    {"excerpt": "C3"},
                    {"excerpt": "C4"},  # only top 3
                ],
            }
        ]
        result = _convert_to_search_results(posts, "test")
        body = result.results[0].body
        assert "Test Title" in body
        # selftext truncated to 300
        assert len(body.split("A" * 300 + "A")[0]) > 0  # no second 300 block
        assert "Top comments: C1 | C2 | C3" in body
        assert "C4" not in body

    def test_post_with_minimal_data(self):
        """Post missing selftext and comments."""
        posts = [{"title": "Minimal", "url": "https://r/1"}]
        result = _convert_to_search_results(posts, "test")
        assert result.results[0].body == "Minimal"

    def test_post_no_title(self):
        """Post missing title defaults to 'Reddit post'."""
        posts = [{"url": "https://r/1"}]
        result = _convert_to_search_results(posts, "test")
        assert result.results[0].title == "Reddit post"

    def test_empty_posts(self):
        """Empty post list returns empty SearchResponse."""
        result = _convert_to_search_results([], "test")
        assert result.total_results == 0
        assert result.results == []


# ============================================================================
# reddit/__init__.py — reddit_rss_search
# ============================================================================


class TestRedditRSSSearch:
    """Tests for the direct RSS search entry point."""

    @patch("web_search_mcp.reddit.parsers.search_rss")
    def test_rss_search_basic(self, mock_rss):
        """reddit_rss_search calls parsers.search_rss."""
        mock_rss.return_value = [{"title": "RSS Post", "url": "https://r/1"}]
        result = reddit_rss_search("test query")
        assert len(result) == 1
        assert result[0]["title"] == "RSS Post"
        mock_rss.assert_called_once_with(query="test query", depth="default", subreddits=None)

    @patch("web_search_mcp.reddit.parsers.search_rss")
    def test_rss_search_with_params(self, mock_rss):
        """reddit_rss_search passes params and respects depth limits."""
        mock_rss.return_value = []
        reddit_rss_search("test", depth="quick", subreddits=["Python"], max_results=5)
        mock_rss.assert_called_once_with(query="test", depth="quick", subreddits=["Python"])

    @patch("web_search_mcp.reddit.parsers.search_rss")
    def test_rss_search_depth_cap(self, mock_rss):
        """Depth cap applies: quick=10."""
        mock_rss.return_value = [{"title": f"P{i}"} for i in range(20)]
        result = reddit_rss_search("test", depth="quick", max_results=100)
        assert len(result) <= 10


# ============================================================================
# reddit/parsers.py — edge cases
# ============================================================================


class TestParsers:
    """Edge cases for RSS and Shreddit parsers."""

    def test_parse_feed_empty(self):
        """Empty XML returns empty list."""
        assert parsers._parse_feed("") == []

    def test_parse_feed_malformed_xml(self):
        """Malformed XML returns empty list."""
        assert parsers._parse_feed("<<<not xml>>>") == []

    def test_parse_feed_missing_link(self):
        """Entry without a link is skipped."""
        xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>No Link</title></entry>
</feed>"""
        posts = parsers._parse_feed(xml)
        assert len(posts) == 0

    def test_parse_feed_entry_with_non_comment_url(self):
        """Entry with a URL not containing /comments/ is skipped."""
        xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Not a comment</title>
    <link href="https://www.reddit.com/r/test/someother"/>
  </entry>
</feed>"""
        posts = parsers._parse_feed(xml)
        assert len(posts) == 0

    def test_parse_feed_valid_entry(self):
        """Valid Atom entry produces a post dict."""
        xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Hello World</title>
    <link href="https://www.reddit.com/r/test/comments/abc/hello_world/"/>
    <author><name>user123</name></author>
    <category term="testsub"/>
    <updated>2026-06-01T12:00:00Z</updated>
  </entry>
</feed>"""
        posts = parsers._parse_feed(xml, query="hello")
        assert len(posts) == 1
        assert posts[0]["title"] == "Hello World"
        assert posts[0]["subreddit"] == "testsub"
        assert posts[0]["author"] == "user123"
        assert posts[0]["date"] == "2026-06-01"
        assert posts[0]["relevance"] > 0

    def test_parse_feed_author_deleted(self):
        """[deleted] author is replaced with [deleted]."""
        xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Deleted Author</title>
    <link href="https://www.reddit.com/r/test/comments/abc/x/"/>
    <author><name>[deleted]</name></author>
    <category term="test"/>
    <updated>2026-01-01T00:00:00Z</updated>
  </entry>
</feed>"""
        posts = parsers._parse_feed(xml)
        assert posts[0]["author"] == "[deleted]"

    def test_parse_feed_content_with_html(self):
        """Content with HTML tags is stripped to text."""
        xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>HTML Content</title>
    <link href="https://www.reddit.com/r/test/comments/abc/y/"/>
    <content type="html">&lt;p&gt;Hello &lt;b&gt;World&lt;/b&gt;&lt;/p&gt;</content>
    <updated>2026-01-01T00:00:00Z</updated>
  </entry>
</feed>"""
        posts = parsers._parse_feed(xml)
        assert "Hello" in posts[0]["selftext"]
        assert "<b>" not in posts[0]["selftext"]

    def test_subreddit_from_empty(self):
        """Empty category and URL returns empty string."""
        result = parsers._subreddit_from("", "https://example.com")
        assert result == ""

    def test_subreddit_from_url(self):
        """URL-based subreddit extraction."""
        result = parsers._subreddit_from("", "https://www.reddit.com/r/python/comments/abc/")
        assert result == "python"

    def test_extract_post_ref(self):
        """Extract post reference tuple from URL."""
        ref = parsers.extract_post_ref("https://www.reddit.com/r/python/comments/abc123/x/")
        assert ref == ("python", "abc123")

    def test_extract_post_ref_invalid_url(self):
        """Invalid URL returns None."""
        assert parsers.extract_post_ref("https://example.com") is None
        assert parsers.extract_post_ref("") is None

    def test_total_comments(self):
        """Extract total-comments attribute."""
        html = '<shreddit-post total-comments="42">'
        assert parsers._total_comments(html) == 42

    def test_total_comments_missing(self):
        """No total-comments attribute returns None."""
        assert parsers._total_comments("<div></div>") is None

    def test_fetch_comments_bad_url(self):
        """fetch_comments with non-Reddit URL returns empty structure."""
        result = parsers.fetch_comments("https://example.com")
        assert result == {"top_comments": [], "comment_insights": [], "num_comments": None}

    def test_fetch_comments_no_html(self):
        """fetch_comments when get_text returns None."""
        with patch("web_search_mcp.reddit.parsers.client.get_text") as mock_get:
            mock_get.return_value = None
            result = parsers.fetch_comments("https://www.reddit.com/r/python/comments/abc/x/")
            assert result == {"top_comments": [], "comment_insights": [], "num_comments": None}

    def test_parse_comments_empty(self):
        """Empty HTML returns empty list."""
        assert parsers.parse_comments("") == []

    def test_parse_comments_deleted_author(self):
        """Deleted author comment is skipped."""
        html = '<shreddit-comment author="[deleted]" thingId="t1_1" score="10" permalink="/p/1"/>'
        assert parsers.parse_comments(html) == []

    def test_parse_comments_no_body(self):
        """Comment without body is skipped."""
        html = '<shreddit-comment author="user" thingId="t1_1" score="10" permalink="/p/1"/>'
        assert parsers.parse_comments(html) == []

    def test_parse_comments_parse_error_score(self):
        """Non-integer score defaults to 0."""
        html = (
            '<shreddit-comment author="user" thingId="t1_1" score="NaN" permalink="/p/1">'
            '<div id="t1_1-post-rtjson-content"><p>body text</p></div>'
            "</shreddit-comment>"
        )
        comments = parsers.parse_comments(html)
        assert len(comments) == 1
        assert comments[0]["score"] == 0

    def test_parse_comments_sorts_by_score(self):
        """Comments are sorted descending by score."""
        html = (
            '<shreddit-comment author="user" thingId="t1_a" score="5" permalink="/p/a">'
            '<div id="t1_a-post-rtjson-content"><p>Low</p></div>'
            "</shreddit-comment>"
            '<shreddit-comment author="user" thingId="t1_b" score="50" permalink="/p/b">'
            '<div id="t1_b-post-rtjson-content"><p>High</p></div>'
            "</shreddit-comment>"
        )
        comments = parsers.parse_comments(html)
        assert comments[0]["score"] == 50
        assert comments[1]["score"] == 5

    def test_build_urls_global(self):
        """Global search without subreddits produces only general RSS URL."""
        urls = parsers._build_urls("test", "default", None)
        assert len(urls) == 1
        assert "search.rss" in urls[0]

    def test_build_urls_with_subreddits(self):
        """Subreddit targeting adds search and listing URLs."""
        urls = parsers._build_urls("test", "default", ["Python"])
        assert len(urls) >= 2
        assert any("r/Python" in u for u in urls)

    def test_build_urls_strips_r_prefix(self):
        """Subreddits with r/ prefix are normalized."""
        urls = parsers._build_urls("test", "quick", ["r/Python"])
        assert any("r/Python" in u for u in urls)

    def test_build_urls_skips_empty(self):
        """Empty subreddit after stripping r/ is skipped."""
        urls = parsers._build_urls("test", "quick", ["r/"])
        assert len(urls) == 1  # only the global URL


# ============================================================================
# reddit/engine.py — edge cases
# ============================================================================


class TestEngine:
    """Edge cases for the engine module."""

    def test_extract_core_subject_preserves_vs(self):
        """'vs' is preserved as a meaningful keyword."""
        assert "vs" in engine._extract_core_subject("Claude Code vs Copilot")

    def test_extract_core_subject_strips_noise_words(self):
        """Noise words are filtered out."""
        result = engine._extract_core_subject("What is the best way to learn Python async")
        assert "best" not in result
        assert "the" not in result
        assert "python" in result

    def test_infer_query_intent_prediction(self):
        """Prediction intent detection."""
        assert engine._infer_query_intent("Bitcoin price prediction 2026") == "prediction"
        assert engine._infer_query_intent("predict the outcome of the election") == "prediction"

    def test_infer_query_intent_product(self):
        """Product intent detection."""
        assert engine._infer_query_intent("best laptop for programming") == "product"
        assert engine._infer_query_intent("Claude Code features") == "product"
        assert engine._infer_query_intent("pricing of OpenAI API") == "product"

    def test_apply_scores(self):
        """_apply_scores updates score and num_comments in-place."""
        post = {"score": 0, "num_comments": 0, "engagement": {"score": 0, "num_comments": 0}}
        scored = {"score": 100, "num_comments": 25}
        engine._apply_scores(post, scored)
        assert post["score"] == 100
        assert post["num_comments"] == 25
        assert post["engagement"]["score"] == 100
        assert post["engagement"]["num_comments"] == 25

    def test_merge_dedupe_respects_first_occurrence(self):
        """First URL occurrence wins in merge."""
        p1 = {"url": "https://r/1", "title": "First"}
        p2 = {"url": "https://r/1", "title": "Second"}
        result = engine._merge_dedupe([[p1], [p2]])
        assert len(result) == 1
        assert result[0]["title"] == "First"

    def test_merge_dedupe_empty_urls(self):
        """Posts with empty URLs are skipped."""
        p1 = {"url": "", "title": "Empty URL"}
        result = engine._merge_dedupe([[p1]])
        assert len(result) == 0


# ============================================================================
# reddit/client.py — edge cases
# ============================================================================


class TestClient:
    """Edge cases for the HTTP client module."""

    def test_http_error_init(self):
        """HTTPError stores status_code and body."""
        err = HTTPError("Not Found", status_code=404, body="{}")
        assert err.status_code == 404
        assert err.body == "{}"

    def test_is_dns_failure_true(self):
        """URLError with gaierror reason is a DNS failure."""
        import urllib.error
        import socket

        err = urllib.error.URLError(socket.gaierror("Name or service not known"))
        assert _is_dns_failure(err) is True

    def test_is_dns_failure_false(self):
        """URLError with non-gaierror reason is not a DNS failure."""
        import urllib.error

        err = urllib.error.URLError("Connection refused")
        assert _is_dns_failure(err) is False

    def test_should_retry_http_429(self):
        """429 status is retried."""
        err = HTTPError("rate limited", status_code=429)
        assert _should_retry_http(err) is True

    def test_should_retry_http_500(self):
        """500 status is retried."""
        err = HTTPError("server error", status_code=500)
        assert _should_retry_http(err) is True

    def test_should_retry_http_400(self):
        """400 status is NOT retried."""
        err = HTTPError("bad request", status_code=400)
        assert _should_retry_http(err) is False

    def test_should_retry_http_dns(self):
        """DNS failure retried."""
        import urllib.error
        import socket

        err = urllib.error.URLError(socket.gaierror("DNS failure"))
        assert _should_retry_http(err) is True

    def test_should_retry_http_non_http(self):
        """Non-HTTP error is not retried."""
        assert _should_retry_http(ValueError("nope")) is False

    def test_request_http_error_400(self):
        """Non-retryable HTTP error raises HTTPError (wrapped by tenacity RetryError)."""
        import urllib.error

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://example.com", 404, "Not Found", {}, None
            )
            with pytest.raises(tenacity.RetryError) as exc_info:
                reddit_client.request("GET", "http://example.com")
            inner = exc_info.value.last_attempt.exception()
            assert isinstance(inner, HTTPError)
            assert inner.status_code == 404

    def test_request_json_decode_error(self):
        """Invalid JSON raises HTTPError (wrapped by tenacity RetryError)."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(tenacity.RetryError) as exc_info:
                reddit_client.request("GET", "http://example.com")
            inner = exc_info.value.last_attempt.exception()
            assert isinstance(inner, HTTPError)
            assert "Invalid JSON" in str(inner)

    def test_request_connection_error(self):
        """Connection errors raise HTTPError (wrapped by tenacity RetryError)."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = ConnectionResetError("Connection reset")
            with pytest.raises(tenacity.RetryError) as exc_info:
                reddit_client.request("GET", "http://example.com")
            inner = exc_info.value.last_attempt.exception()
            assert isinstance(inner, HTTPError)
            assert "Connection error" in str(inner)

    def test_get_returns_empty_on_error(self):
        """get() returns {} on HTTPError."""
        from unittest.mock import patch as mock_patch

        with mock_patch("web_search_mcp.reddit.client.request") as mock_request:
            mock_request.side_effect = HTTPError("fail")
            result = reddit_client.get("http://example.com")
            assert result == {}

    def test_get_text_returns_none_on_error(self):
        """get_text() returns None on HTTPError."""
        from unittest.mock import patch as mock_patch

        with mock_patch("web_search_mcp.reddit.client.request") as mock_request:
            mock_request.side_effect = HTTPError("fail")
            result = reddit_client.get_text("http://example.com")
            assert result is None

    def test_get_text_returns_string(self):
        """get_text() returns text on success."""
        from unittest.mock import patch as mock_patch

        with mock_patch("web_search_mcp.reddit.client.request") as mock_request:
            mock_request.return_value = "<html>content</html>"
            result = reddit_client.get_text("http://example.com")
            assert result == "<html>content</html>"

    def test_search_json_empty_on_exception(self):
        """search_json returns [] on exception."""
        from unittest.mock import patch as mock_patch

        with mock_patch("web_search_mcp.reddit.client.get") as mock_get:
            mock_get.side_effect = Exception("fail")
            result = reddit_client.search_json("test")
            assert result == []


# ============================================================================
# reddit/models.py — listing edge cases
# ============================================================================


class TestListingModels:
    """Edge cases for listing card parsing."""

    def test_parse_listing_basic_post(self):
        """Parse a basic shreddit-post element."""
        html = """<shreddit-post
            post-id="abc123"
            title="Test Post"
            score="42"
            comment-count="7"
            author="testuser"
            permalink="/r/test/comments/abc123/test_post/"
            created-timestamp="2026-06-01T12:00:00Z"
        ></shreddit-post>"""
        posts = listing_models._parse_listing(html, "test", "test query")
        assert len(posts) == 1
        assert posts[0]["title"] == "Test Post"
        assert posts[0]["score"] == 42
        assert posts[0]["num_comments"] == 7
        assert posts[0]["author"] == "testuser"
        assert "test_post" in posts[0]["url"]
        assert posts[0]["subreddit"] == "test"
        assert posts[0]["date"] == "2026-06-01"

    def test_parse_listing_empty_html(self):
        """Empty HTML returns empty list."""
        assert listing_models._parse_listing("", "test", "") == []

    def test_parse_listing_no_post_id(self):
        """Post element without post-id is skipped."""
        html = """<shreddit-post title="No ID"></shreddit-post>"""
        posts = listing_models._parse_listing(html, "test", "")
        assert len(posts) == 0

    def test_parse_listing_missing_fields(self):
        """Post with only post-id has defaults for missing fields."""
        html = """<shreddit-post post-id="abc"></shreddit-post>"""
        posts = listing_models._parse_listing(html, "test", "")
        assert len(posts) == 1
        assert posts[0]["title"] == ""
        assert posts[0]["score"] == 0
        assert posts[0]["num_comments"] == 0
        assert posts[0]["author"] == "[deleted]"

    def test_parse_listing_score_not_digit(self):
        """Non-numeric score defaults to 0."""
        html = """<shreddit-post
            post-id="abc"
            title="Test"
            score="N/A"
            comment-count="3"
            author="user"
            permalink="/r/test/comments/abc/x/"
            created-timestamp="2026-01-01T00:00:00Z"
        ></shreddit-post>"""
        posts = listing_models._parse_listing(html, "test", "")
        assert posts[0]["score"] == 0

    def test_parse_listing_engagement(self):
        """Engagement dict contains score and num_comments."""
        html = """<shreddit-post
            post-id="abc"
            title="Test"
            score="99"
            comment-count="10"
            author="user"
            permalink="/r/test/comments/abc/x/"
            created-timestamp="2026-01-01T00:00:00Z"
        ></shreddit-post>"""
        posts = listing_models._parse_listing(html, "test", "")
        assert posts[0]["engagement"]["score"] == 99
        assert posts[0]["engagement"]["num_comments"] == 10
        assert posts[0]["engagement"]["upvote_ratio"] is None

    def test_fetch_listing_fetch_failure(self):
        """_fetch_listing returns [] on failure."""
        with patch("web_search_mcp.reddit.models.client.get_text") as mock_get:
            mock_get.return_value = None
            result = listing_models._fetch_listing("test", "top", "default", "query")
            assert result == []

    def test_fetch_listing_parse_result(self):
        """_fetch_listing returns parsed posts."""
        with patch("web_search_mcp.reddit.models.client.get_text") as mock_get:
            mock_get.return_value = """<shreddit-post
                post-id="abc" title="Test" score="10" comment-count="2"
                author="u" permalink="/r/test/comments/abc/x/"
                created-timestamp="2026-01-01T00:00:00Z"
            ></shreddit-post>"""
            result = listing_models._fetch_listing("test", "top", "default", "query")
            assert len(result) == 1
            assert result[0]["title"] == "Test"

    def test_iso_to_date_none(self):
        """_iso_to_date returns None for None input."""
        assert listing_models._iso_to_date(None) is None

    def test_iso_to_date_invalid(self):
        """_iso_to_date returns None for invalid input."""
        assert listing_models._iso_to_date("not-a-date") is None

    def test_iso_to_epoch_none(self):
        """_iso_to_epoch returns None for None input."""
        assert listing_models._iso_to_epoch(None) is None

    def test_iso_to_epoch_invalid(self):
        """_iso_to_epoch returns None for invalid input."""
        assert listing_models._iso_to_epoch("not-a-date") is None

    def test_post_id_extraction(self):
        """_post_id extracts post ID from URL."""
        result = listing_models._post_id("https://www.reddit.com/r/test/comments/abc123/x/")
        assert result == "abc123"

    def test_post_id_no_match(self):
        """_post_id returns empty string for URL without comments."""
        assert listing_models._post_id("https://example.com") == ""
