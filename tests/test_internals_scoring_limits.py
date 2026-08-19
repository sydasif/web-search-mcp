"""Offline unit tests for shared scoring helpers and depth/timeout constants."""

from __future__ import annotations

from web_search_mcp._config import limits
from web_search_mcp._utils import scoring


def test_token_overlap_relevance_exact_match() -> None:
    assert scoring.token_overlap_relevance("python asyncio", "python asyncio") == 1.0


def test_token_overlap_relevance_partial_overlap() -> None:
    # 1 of 2 query tokens present -> 0.5
    assert scoring.token_overlap_relevance("python rust", "python guide") == 0.5


def test_token_overlap_relevance_empty_inputs() -> None:
    assert scoring.token_overlap_relevance("", "anything") == 0.0
    assert scoring.token_overlap_relevance("query", "") == 0.0


def test_token_overlap_relevance_no_shared_tokens() -> None:
    assert scoring.token_overlap_relevance("foo bar", "baz qux") == 0.0


def test_compute_relevance_with_query_uses_content_score() -> None:
    score = scoring.compute_relevance(
        query="kubernetes", title="kubernetes tutorial", rank_index=0, engagement=50
    )
    # query present: 0.6*rank(1.0) + 0.4*content(>=0) + engagement_boost
    assert 0.6 <= score <= 1.0


def test_compute_relevance_without_query_uses_rank_only() -> None:
    score = scoring.compute_relevance(query="", title="anything", rank_index=0, engagement=0)
    # no query: 0.7*rank(1.0) + engagement_boost(0) + 0.1 == 0.8
    assert score == 0.8


def test_compute_relevance_decay_with_rank() -> None:
    top = scoring.compute_relevance("q", "q", rank_index=0, engagement=0)
    bottom = scoring.compute_relevance("q", "q", rank_index=20, engagement=0)
    assert top > bottom


def test_compute_relevance_engagement_capped() -> None:
    # Very high engagement must not push past 1.0
    score = scoring.compute_relevance("q", "q", rank_index=0, engagement=10**9)
    assert score <= 1.0


def test_depth_limits_cover_expected_platforms() -> None:
    for platform in ("github", "hackernews", "reddit", "x", "linkedin"):
        assert platform in limits.DEPTH_LIMITS
        assert limits.DEPTH_LIMITS[platform].keys() == {"quick", "default", "deep"}


def test_enrich_limits_exclude_x() -> None:
    # X has no comment-enrichment tier
    assert "x" not in limits.ENRICH_LIMITS
    for platform in ("github", "hackernews", "reddit", "linkedin"):
        assert platform in limits.ENRICH_LIMITS


def test_feed_timeout_is_positive_int() -> None:
    assert isinstance(limits.FEED_TIMEOUT, int)
    assert limits.FEED_TIMEOUT > 0
