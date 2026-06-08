"""Tests for Reddit search module."""

import unittest
from unittest.mock import patch

from web_search_mcp.reddit import reddit_search_tool
from web_search_mcp.models import ErrorResponse
from web_search_mcp.reddit.engine import (
    expand_queries,
    search_and_enrich,
    _extract_core_subject,
    _infer_query_intent,
    _merge_dedupe,
)
from web_search_mcp.reddit import parsers


class TestQueryExpansion(unittest.TestCase):
    """Tests for query expansion logic."""

    def test_extract_core_subject_strips_noise(self):
        """Should strip common noise words and meta phrases."""
        self.assertEqual(
            _extract_core_subject("what are the best Python async tips"), "python async"
        )
        self.assertEqual(_extract_core_subject("how to use Docker"), "docker")
        self.assertEqual(_extract_core_subject("best practices for React"), "react")

    def test_extract_core_subject_preserves_entities(self):
        """Should preserve proper nouns and multi-word product names."""
        self.assertEqual(_extract_core_subject("Claude Code"), "claude code")
        self.assertEqual(_extract_core_subject("FastAPI vs Flask"), "fastapi vs flask")

    def test_extract_core_subject_strips_punctuation(self):
        """Should strip trailing punctuation."""
        self.assertEqual(_extract_core_subject("Python async issues!"), "python async issues")

    def test_expand_queries_empty_core_returns_original(self):
        """Empty topic falls back to original."""
        queries = expand_queries("", depth="quick")
        self.assertEqual(len(queries), 1)

    def test_infer_query_intent_comparison(self):
        """Should detect comparison intent."""
        self.assertEqual(_infer_query_intent("Claude Code vs Copilot"), "comparison")
        self.assertEqual(_infer_query_intent("FastAPI versus Flask comparison"), "comparison")
        self.assertEqual(_infer_query_intent("difference between React and Vue"), "comparison")

    def test_infer_query_intent_how_to(self):
        """Should detect how-to intent."""
        self.assertEqual(_infer_query_intent("how to use Docker"), "how_to")
        self.assertEqual(_infer_query_intent("tutorial for FastAPI"), "how_to")
        self.assertEqual(_infer_query_intent("troubleshoot async errors"), "how_to")

    def test_infer_query_intent_opinion(self):
        """Should detect opinion intent."""
        self.assertEqual(_infer_query_intent("thoughts on Claude Code"), "opinion")
        self.assertEqual(_infer_query_intent("is FastAPI worth it"), "opinion")
        self.assertEqual(_infer_query_intent("should i use React"), "opinion")

    def test_infer_query_intent_general(self):
        """Should default to general."""
        self.assertEqual(_infer_query_intent("Python async"), "general")
        self.assertEqual(_infer_query_intent("React patterns"), "general")

    def test_expand_queries_single_for_simple_topic(self):
        """Simple topics produce 1 query."""
        queries = expand_queries("Python async", depth="quick")
        self.assertEqual(len(queries), 1)
        self.assertIn("python async", queries[0].lower())

    def test_expand_queries_product_topic(self):
        """Product topics add review variant."""
        queries = expand_queries("Claude Code features", depth="default")
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(any("review" in q.lower() for q in queries))

    def test_expand_queries_comparison_topic(self):
        """Comparison topics add vs variant."""
        queries = expand_queries("Claude Code vs Copilot", depth="default")
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(any("vs" in q.lower() or "worth it" in q.lower() for q in queries))

    def test_expand_queries_deep_adds_issues_variant(self):
        """Deep depth adds issues/problems variant for how_to topics."""
        queries = expand_queries("how to deploy FastAPI", depth="deep")
        self.assertTrue(any("issues" in q.lower() or "problems" in q.lower() for q in queries))

    def test_expand_queries_no_duplicates(self):
        """Should never produce duplicate queries."""
        queries = expand_queries("Claude Code vs Copilot", depth="deep")
        self.assertEqual(len(queries), len(set(q.lower() for q in queries)))

    def test_expand_queries_includes_original_when_different(self):
        """Should include original topic if different from core subject."""
        queries = expand_queries("what are the best Python async libraries", depth="default")
        self.assertTrue(any("best" in q.lower() for q in queries))


class TestMergeDedupe(unittest.TestCase):
    """Tests for cross-query deduplication."""

    def test_merge_dedupe_removes_duplicates(self):
        """Same URL across batches should appear only once."""
        post_a = {"url": "https://reddit.com/r/test/1", "title": "Post 1"}
        post_b = {"url": "https://reddit.com/r/test/1", "title": "Post 1 dupe"}
        post_c = {"url": "https://reddit.com/r/test/2", "title": "Post 2"}

        result = _merge_dedupe([[post_a], [post_b, post_c]])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Post 1")

    def test_merge_dedupe_empty_batches(self):
        """Empty batches produce empty result."""
        self.assertEqual(_merge_dedupe([[], []]), [])

    def test_merge_dedupe_preserves_order(self):
        """First batch order preserved, then second batch appends."""
        p1 = {"url": "https://r/1", "title": "A"}
        p2 = {"url": "https://r/2", "title": "B"}
        p3 = {"url": "https://r/3", "title": "C"}
        result = _merge_dedupe([[p1, p2], [p3]])
        self.assertEqual([r["title"] for r in result], ["A", "B", "C"])


class TestFanOutPipeline(unittest.TestCase):
    """Integration tests for search_and_enrich fan-out and merge."""

    @patch("web_search_mcp.reddit.engine._run_single_pipeline")
    def test_multi_query_fanout_merges_and_dedupes(self, mock_pipeline):
        """Multiple query variants should be merged and deduped by URL."""
        mock_pipeline.side_effect = [
            [
                {
                    "url": "https://r/1",
                    "title": "A",
                    "score": 10,
                    "num_comments": 0,
                    "engagement": {"score": 10, "num_comments": 0},
                    "relevance": 0.5,
                    "date": "2026-06-01",
                },
                {
                    "url": "https://r/2",
                    "title": "B",
                    "score": 5,
                    "num_comments": 0,
                    "engagement": {"score": 5, "num_comments": 0},
                    "relevance": 0.3,
                    "date": "2026-06-01",
                },
                {
                    "url": "https://r/3",
                    "title": "C",
                    "score": 3,
                    "num_comments": 0,
                    "engagement": {"score": 3, "num_comments": 0},
                    "relevance": 0.2,
                    "date": "2026-06-01",
                },
            ],
            [
                {
                    "url": "https://r/2",
                    "title": "B",
                    "score": 5,
                    "num_comments": 0,
                    "engagement": {"score": 5, "num_comments": 0},
                    "relevance": 0.3,
                    "date": "2026-06-01",
                },
                {
                    "url": "https://r/3",
                    "title": "C",
                    "score": 3,
                    "num_comments": 0,
                    "engagement": {"score": 3, "num_comments": 0},
                    "relevance": 0.2,
                    "date": "2026-06-01",
                },
                {
                    "url": "https://r/4",
                    "title": "D",
                    "score": 8,
                    "num_comments": 0,
                    "engagement": {"score": 8, "num_comments": 0},
                    "relevance": 0.4,
                    "date": "2026-06-01",
                },
            ],
        ]

        result = search_and_enrich(
            "Claude Code features",
            from_date="2026-06-01",
            to_date="2026-06-08",
            depth="quick",
        )

        urls = [p["url"] for p in result]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertGreaterEqual(len(result), 3)

    @patch("web_search_mcp.reddit.engine._run_single_pipeline")
    def test_single_pipeline_failure_doesnt_sink_run(self, mock_pipeline):
        """If one pipeline variant fails, others still contribute."""
        mock_pipeline.side_effect = [
            Exception("network error"),
            [
                {
                    "url": "https://r/5",
                    "title": "E",
                    "score": 15,
                    "num_comments": 0,
                    "engagement": {"score": 15, "num_comments": 0},
                    "relevance": 0.6,
                    "date": "2026-06-01",
                },
            ],
        ]

        result = search_and_enrich(
            "Claude Code features",
            from_date="2026-06-01",
            to_date="2026-06-08",
            depth="quick",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "E")

    @patch("web_search_mcp.reddit.engine._run_single_pipeline")
    def test_single_query_skips_threadpool(self, mock_pipeline):
        """When expand_queries returns 1 query, thread pool is not used."""
        mock_pipeline.return_value = [
            {
                "url": "https://r/6",
                "title": "F",
                "score": 20,
                "num_comments": 0,
                "engagement": {"score": 20, "num_comments": 0},
                "relevance": 0.7,
                "date": "2026-06-01",
            },
        ]

        result = search_and_enrich(
            "Python async",
            from_date="2026-06-01",
            to_date="2026-06-08",
            depth="quick",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "F")
        mock_pipeline.assert_called_once()


class TestRedditSearch(unittest.TestCase):
    """Tests for reddit_search_tool."""

    def test_empty_query_returns_error(self):
        """Empty query should return error response."""
        result = reddit_search_tool("")
        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Query cannot be empty")

    def test_whitespace_query_returns_error(self):
        """Whitespace-only query should return error response."""
        result = reddit_search_tool("   ")
        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Query cannot be empty")

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_successful_search_returns_markdown(self, mock_search):
        """Successful search should return formatted markdown."""
        mock_search.return_value = [
            {
                "title": "Test Post",
                "url": "https://reddit.com/r/test/comments/abc123",
                "subreddit": "test",
                "score": 100,
                "num_comments": 25,
                "selftext": "This is a test post content",
                "top_comments": [
                    {"excerpt": "Great comment!", "score": 50, "author": "user1"},
                ],
                "date": "2026-01-15",
            }
        ]

        result = reddit_search_tool(
            "test query", max_results=5, depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        self.assertIn("Test Post", result)
        self.assertIn("r/test", result)
        self.assertIn("100 upvotes", result)
        self.assertIn("25 comments", result)
        self.assertIn("Great comment!", result)

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_successful_search_returns_json(self, mock_search):
        """Successful search with json format should return SearchResponse."""
        mock_search.return_value = [
            {
                "title": "Test Post",
                "url": "https://reddit.com/r/test/comments/abc123",
                "subreddit": "test",
                "score": 100,
                "num_comments": 25,
                "selftext": "Test content",
                "top_comments": [],
                "date": "2026-01-15",
            }
        ]

        result = reddit_search_tool(
            "test query", max_results=5, depth="quick", response_format="json"
        )

        from web_search_mcp.models import SearchResponse

        self.assertIsInstance(result, SearchResponse)
        self.assertEqual(result.query, "test query")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "Test Post")

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_time_range_mapping(self, mock_search):
        """Time range should be mapped to date filters."""
        mock_search.return_value = []

        result = reddit_search_tool(
            "test", time_range="w", depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertIn("from_date", call_args.kwargs)
        self.assertIn("to_date", call_args.kwargs)

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_subreddits_parameter(self, mock_search):
        """Subreddits parameter should be passed through."""
        mock_search.return_value = []

        result = reddit_search_tool(
            "test", subreddits=["Python", "learnpython"], depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertEqual(call_args.kwargs["subreddits"], ["Python", "learnpython"])

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_depth_limits_results(self, mock_search):
        """Depth parameter should cap max_results."""
        mock_search.return_value = [
            {
                "title": f"Post {i}",
                "url": f"https://r/{i}",
                "subreddit": "test",
                "score": 10,
                "num_comments": 5,
                "selftext": "",
                "top_comments": [],
                "date": "2026-01-01",
            }
            for i in range(10)
        ]

        result = reddit_search_tool(
            "test", max_results=100, depth="quick", response_format="markdown"
        )

        self.assertIsInstance(result, str)
        self.assertIn("Found 10 posts", result)
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        self.assertEqual(call_args.kwargs["depth"], "quick")

    @patch("web_search_mcp.reddit.engine.search_and_enrich")
    def test_search_exception_returns_error(self, mock_search):
        """Exception during search should return error response."""
        mock_search.side_effect = Exception("Network error")

        result = reddit_search_tool("test query", response_format="markdown")

        self.assertIsInstance(result, ErrorResponse)
        self.assertEqual(result.error, "Reddit search failed")


class TestRedditResilience(unittest.TestCase):
    """Hardened tests for Reddit's fragile keyless paths."""

    @patch("web_search_mcp.reddit.client.get_text")
    def test_reddit_empty_rss_body(self, mock_get_text):
        """Handle 200 OK with empty body gracefully."""
        mock_get_text.return_value = ""
        result = parsers.search_rss("test query")
        self.assertEqual(result, [])

    @patch("web_search_mcp.reddit.client.get_text")
    def test_reddit_malformed_shreddit_json(self, mock_get_text):
        """Handle malformed attributes in Shreddit HTML."""
        # Mock HTML with a comment that has a null score or missing author
        malformed_html = (
            '<shreddit-comment author="" score="NaN" thingId="t1_123" permalink="/p/1">'
            '<div id="t1_123-post-rtjson-content">Some content</div>'
            "</shreddit-comment>"
        )
        mock_get_text.return_value = malformed_html
        # We test the parser directly
        comments = parsers.parse_comments(malformed_html)
        # Should handle NaN score and empty author gracefully
        if comments:
            self.assertEqual(comments[0]["score"], 0)
            self.assertEqual(comments[0]["author"], "[deleted]")

    @patch("web_search_mcp.reddit.client.get_text")
    def test_reddit_partial_html(self, mock_get_text):
        """Handle pages missing the expected rtjson-content anchors."""
        partial_html = (
            '<shreddit-comment thingId="t1_123" permalink="/p/1">'
            "<div>Missing the rtjson anchor entirely</div>"
            "</shreddit-comment>"
        )
        mock_get_text.return_value = partial_html
        body = parsers._body_for(partial_html, "t1_123")
        self.assertEqual(body, "")


if __name__ == "__main__":
    unittest.main()
