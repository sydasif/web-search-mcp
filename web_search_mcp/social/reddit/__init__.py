"""Reddit search tool for MCP — keyless, free Reddit search."""

from __future__ import annotations

import logging
from typing import Any

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._models import ErrorResponse, SearchResponse, SearchResult, build_search_response
from ..._models.types import Depth, ResponseFormat
from ..._utils import format_error, time_range_to_date_window
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
    if not query or not query.strip():
        return format_error("Query cannot be empty")

    from_date, to_date = time_range_to_date_window(time_range)

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
            # Format as markdown
            lines = [f"# Reddit Search Results for '{query}'", f"Found {len(posts)} posts.", ""]
            for i, post in enumerate(posts, 1):
                lines.append(
                    f"{i}. **[{post.get('title', 'Reddit post')}]({post.get('url', '#')})**",
                )
                sub = post.get("subreddit", "unknown")
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)
                lines.append(
                    f"   r/{sub} • {score} upvotes • {comments} comments",
                )
                if post.get("selftext"):
                    lines.append(f"   {post['selftext'][:200]}...")
                if post.get("top_comments"):
                    lines.append(
                        f"   Top comment: {post['top_comments'][0].get('excerpt', '')[:150]}...",
                    )
                lines.append("")
            return "\n".join(lines)

        return response

    except Exception as e:
        logger.exception("Reddit search failed for query %r", query)
        return format_error("Reddit search failed", str(e))
