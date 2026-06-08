"""Reddit search tool for MCP — keyless, free Reddit search."""

import logging
from datetime import datetime
from typing import List, Optional, Literal

from ..models import SearchResponse, SearchResult, ErrorResponse
from ..utils import format_error
from . import engine, parsers

logger = logging.getLogger("web-search-mcp")


def _convert_to_search_results(
    posts: List[dict], query: str, search_type: Literal["text", "news"] = "text"
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
    time_range: Optional[str] = None,
    depth: Literal["quick", "default", "deep"] = "default",
    subreddits: Optional[List[str]] = None,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Reddit via keyless RSS + shreddit enrichment — free, no API key needed.

    Role: Discovery. Use this for Reddit-specific discussions, opinions, and
    community insights. Alternative: web_search for general web results,
    groq_research for synthesized multi-source research.

    Workflow: Three-tier keyless pipeline:
    - Tier 0: Legacy .json search (often 403, tried once)
    - Tier 1: RSS discovery (load-bearing, robust)
    - Tier 2: Shreddit comment enrichment for top posts

    Args:
        query: Search query string
        search_type: Type of search (only 'text' supported for Reddit)
        max_results: Max results (capped by depth: quick=10, default=25, deep=50)
        time_range: Time filter ('d', 'w', 'm', 'y') — mapped to date range
        depth: Search depth — controls result limits and enrichment
        subreddits: Optional list of subreddit names to target (without r/)
        response_format: Output format ('json' or 'markdown')

    Returns:
        SearchResponse with Reddit posts including scores, comments, and insights
    """
    if not query or not query.strip():
        return format_error("Query cannot be empty")

    # Map time_range to from_date / to_date
    today = datetime.now().date()
    from_date = "2000-01-01"
    to_date = today.isoformat()

    if time_range:
        from datetime import timedelta

        if time_range == "d":
            from_date = (today - timedelta(days=1)).isoformat()
        elif time_range == "w":
            from_date = (today - timedelta(weeks=1)).isoformat()
        elif time_range == "m":
            from_date = (today - timedelta(weeks=4)).isoformat()
        elif time_range == "y":
            from_date = (today - timedelta(weeks=52)).isoformat()

    # Respect depth limits
    depth_limits = {"quick": 10, "default": 25, "deep": 50}
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
                    f"{i}. **[{post.get('title', 'Reddit post')}]({post.get('url', '#')})**"
                )
                lines.append(
                    f"   r/{post.get('subreddit', 'unknown')} • {post.get('score', 0)} upvotes • {post.get('num_comments', 0)} comments"
                )
                if post.get("selftext"):
                    lines.append(f"   {post['selftext'][:200]}...")
                if post.get("top_comments"):
                    lines.append(
                        f"   Top comment: {post['top_comments'][0].get('excerpt', '')[:150]}..."
                    )
                lines.append("")
            return "\n".join(lines)

        return response

    except Exception as e:
        logger.exception("Reddit search failed for query %r", query)
        return format_error("Reddit search failed", str(e))


def reddit_rss_search(
    query: str,
    depth: Literal["quick", "default", "deep"] = "default",
    subreddits: Optional[List[str]] = None,
    max_results: int = 25,
) -> List[dict]:
    """Direct access to Reddit RSS discovery (Tier 1 only, no enrichment).

    Faster but no comment enrichment or score backfill. Use when you need
    raw discovery speed or want to control enrichment yourself.

    Args:
        query: Search query string
        depth: Search depth
        subreddits: Optional target subreddits
        max_results: Max results to return

    Returns:
        List of post dicts with placeholder scores
    """
    depth_limits = {"quick": 10, "default": 25, "deep": 50}
    max_results = min(max_results, depth_limits.get(depth, 25))

    return parsers.search_rss(query=query, depth=depth, subreddits=subreddits)[:max_results]
