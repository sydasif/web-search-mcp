"""Reddit search tool for MCP — keyless, free Reddit search."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._models import ErrorResponse, SearchResponse, SearchResult, build_search_response
from ..._models.types import Depth, ResponseFormat
from ..._utils import format_error, format_results_markdown, validate_query
from . import engine

logger = logging.getLogger(__name__)


def _build_results(posts: list[dict[str, Any]]) -> list[SearchResult]:
    """Convert reddit_engine posts to SearchResult list."""
    results = []
    for post in posts:
        body_parts = []
        if post.get("title"):
            body_parts.append(post["title"])
        if post.get("selftext"):
            body_parts.append(post["selftext"][:300])
        if post.get("top_comments"):
            comments_text = " | ".join(c.get("excerpt", "") for c in post["top_comments"][:3])
            body_parts.append(f"Top comments: {comments_text}")

        result = SearchResult(
            title=post.get("title", "Reddit post"),
            href=post.get("url", ""),
            url=post.get("url", ""),
            body=" ".join(body_parts) if body_parts else None,
        )
        results.append(result)
    return results


def reddit_search_tool(
    query: str,
    max_results: int = 25,
    time_range: str | None = None,
    depth: Depth = "default",
    subreddits: list[str] | None = None,
    response_format: ResponseFormat = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Reddit via keyless RSS + shreddit enrichment — free, no API key needed."""
    if error := validate_query(query):
        return error

    # Map time_range to from_date / to_date
    today = datetime.now().date()
    from_date = "2000-01-01"
    to_date = today.isoformat()

    if time_range:
        if time_range == "d":
            from_date = (today - timedelta(days=1)).isoformat()
        elif time_range == "w":
            from_date = (today - timedelta(weeks=1)).isoformat()
        elif time_range == "m":
            from_date = (today - timedelta(weeks=4)).isoformat()
        elif time_range == "y":
            from_date = (today - timedelta(weeks=52)).isoformat()

    # Respect depth limits
    depth_limits = _ALL_DEPTH_LIMITS["reddit"]
    max_results = min(max_results, depth_limits.get(depth, 25))

    try:
        posts = engine.search_and_enrich(
            topic=query,
            from_date=from_date,
            to_date=to_date,
            depth=depth,
            subreddits=subreddits,
        )

        response = build_search_response(_build_results(posts), query)

        if response_format == "markdown":
            return _format_reddit_markdown(posts, query)

        return response

    except Exception as e:
        logger.exception("Reddit search failed for query %r", query)
        return format_error("Reddit search failed", str(e))


def _format_reddit_markdown(posts: list[dict[str, Any]], query: str) -> str:
    """Format Reddit results as markdown."""

    def _item_lines(post: dict[str, Any], i: int) -> list[str]:
        lines = [
            f"{i}. **[{post.get('title', 'Reddit post')}]({post.get('url', '#')})**",
            f"   r/{post.get('subreddit', 'unknown')} "
            f"• {post.get('score', 0)} upvotes "
            f"• {post.get('num_comments', 0)} comments",
        ]
        if post.get("selftext"):
            lines.append(f"   {post['selftext'][:200]}...")
        if post.get("top_comments"):
            lines.append(
                f"   Top comment: {post['top_comments'][0].get('excerpt', '')[:150]}...",
            )
        return lines

    return format_results_markdown(posts, query, "Reddit", "posts", _item_lines)
