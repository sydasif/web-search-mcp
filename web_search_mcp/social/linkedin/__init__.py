"""LinkedIn search tool for MCP — DDG search + Jina AI enrichment.

Searches LinkedIn via DuckDuckGo with site:linkedin.com filter and enriches
results using Jina Reader (r.jina.ai) to bypass bot protection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..._models import ErrorResponse, SearchResponse, SearchResult
from ..._models.types import Depth, ResponseFormat
from ..._utils import format_error
from . import client

logger = logging.getLogger(__name__)


def _convert_to_search_results(
    items: list[dict[str, Any]],
    query: str,
) -> SearchResponse:
    """Convert linkedin_client output to SearchResponse format."""
    results = []
    for item in items:
        name = item.get("name", "LinkedIn result")
        url = item.get("url", "")
        headline = item.get("headline", "")
        snippet = item.get("snippet", "")
        content_type = item.get("content_type", "other")

        # Build body from available fields
        body_parts = []
        if headline:
            body_parts.append(headline)
        if snippet:
            body_parts.append(snippet)
        if item.get("location"):
            body_parts.append(f"Location: {item['location']}")
        if item.get("about"):
            body_parts.append(f"About: {item['about'][:200]}")
        if item.get("content_preview"):
            body_parts.append(f"Preview: {item['content_preview'][:200]}")

        result = SearchResult(
            title=f"[{content_type.title()}] {name}",
            href=url,
            url=url,
            body=" ".join(body_parts) if body_parts else None,
        )
        results.append(result)

    return SearchResponse(
        query=query,
        search_type="text",
        total_results=len(results),
        results=results,
        has_more=False,
        next_page=None,
    )


def linkedin_search_tool(
    query: str,
    max_results: int = 25,
    content_type: str = "all",
    depth: Depth = "default",
    response_format: ResponseFormat = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search LinkedIn via DuckDuckGo + Jina Reader enrichment.

    Role: Professional network search. Use this to find people, companies,
    posts, jobs, and articles on LinkedIn without API authentication.

    Workflow: DDG site:linkedin.com search -> Jina Reader enrichment for clean content.

    Args:
        query: Search query string
        max_results: Max results (capped by depth: quick=10, default=25, deep=50)
        content_type: Filter by type - 'people', 'companies', 'posts', 'jobs', 'articles', 'all'
        depth: Search depth — controls result limits and enrichment
        response_format: Output format ('json' or 'markdown')

    Returns:
        str: Markdown-formatted LinkedIn results (when response_format="markdown")
        SearchResponse: Raw results with structured data (when response_format="json")
        ErrorResponse: Error response if applicable

    Examples:
        - "site reliability engineer google" content_type="people"
        - "machine learning startup" content_type="companies"
        - "kubernetes" content_type="posts"
        - "software engineer remote" content_type="jobs"
        - "AI ethics" content_type="articles"

    Error Handling:
        - Empty query: Returns error message
        - No results: Returns empty results
        - Network/Jina errors: Logged, partial results returned

    """
    if not query or not query.strip():
        return format_error("Query cannot be empty")

    try:
        items = client.search_linkedin(
            query=query,
            content_type=content_type,
            max_results=max_results,
            depth=depth,
        )

        response = _convert_to_search_results(items, query)

        if response_format == "markdown":
            return _format_linkedin_markdown(items, query)

        return response

    except Exception as e:
        logger.exception("LinkedIn search failed for query %r", query)
        return format_error("LinkedIn search failed", str(e))


def _format_linkedin_markdown(items: list[dict[str, Any]], query: str) -> str:
    """Format LinkedIn results as markdown."""

    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        name = item.get("name", "Unknown")
        url = item.get("url", "#")
        headline = item.get("headline", "")
        snippet = item.get("snippet", "")
        content_type = item.get("content_type", "other")

        emoji = client._TYPE_EMOJI.get(content_type, client._TYPE_EMOJI["other"])

        lines: list[str] = [
            f"{i}. {emoji} **[{name}]({url})**",
        ]
        if headline:
            lines.append(f"   {headline}")
        if snippet:
            lines.append(f"   {snippet[:200]}{'...' if len(snippet) > 200 else ''}")

        if item.get("location"):
            lines.append(f"   \U0001f4cd {item['location']}")
        if item.get("about"):
            lines.append(f"   {item['about'][:200]}...")
        if item.get("content_preview"):
            lines.append(f"   {item['content_preview'][:200]}...")

        return lines

    # Simple markdown formatting
    lines = [f"# LinkedIn Search Results for '{query}'", f"Found {len(items)} results.", ""]
    for i, item in enumerate(items, 1):
        lines.extend(_item_lines(item, i))
        lines.append("")

    return "\n".join(lines)


__all__ = ["linkedin_search_tool", "client"]
