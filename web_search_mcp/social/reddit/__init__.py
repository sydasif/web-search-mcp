"""Reddit search tool for MCP — keyless, free Reddit search."""

import logging
from datetime import datetime, timedelta
from typing import Literal

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._models import ErrorResponse, SearchResponse, SearchResult
from ..._utils import format_error
from . import engine

logger = logging.getLogger(__name__)


def _convert_to_search_results(
    posts: list[dict],
    query: str,
    search_type: Literal["text", "news"] = "text",
) -> SearchResponse:
    """Convert reddit_engine output to SearchResponse format."""
    results = []
    for post in posts:
        # Build body from title + selftext + top comments if available
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

    return SearchResponse(
        query=query,
        search_type=search_type,
        total_results=len(results),
        results=results,
        has_more=False,
        next_page=None,
    )


def reddit_search_tool(
    query: str,
    search_type: Literal["text", "news"] = "text",
    max_results: int = 25,
    time_range: str | None = None,
    depth: Literal["quick", "default", "deep"] = "default",
    subreddits: list[str] | None = None,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Reddit via keyless RSS + shreddit enrichment — free, no API key needed."""
    if not query or not query.strip():
        return format_error("Query cannot be empty")

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

        response = _convert_to_search_results(posts, query, search_type)

        if response_format == "markdown":
            # Format as markdown
            lines = [f"# Reddit Search Results for '{query}'", f"Found {len(posts)} posts.", ""]
            for i, post in enumerate(posts, 1):
                lines.append(
                    f"{i}. **[{post.get('title', 'Reddit post')}]({post.get('url', '#')})**",
                )
                lines.append(
                    f"   r/{post.get('subreddit', 'unknown')} • {post.get('score', 0)} upvotes • {post.get('num_comments', 0)} comments",
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
