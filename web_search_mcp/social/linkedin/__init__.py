"""LinkedIn search tool for MCP — DDG search + Jina AI enrichment.

Searches LinkedIn via DuckDuckGo with site:linkedin.com filter and enriches
results using Jina Reader (r.jina.ai) to bypass bot protection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..._models import ErrorResponse, SearchResponse, SearchResult, build_search_response
from ..._models.types import Depth, ResponseFormat
from ..._utils import format_error, validate_query
from . import client

logger = logging.getLogger(__name__)


def _build_results(items: list[dict[str, Any]]) -> list[SearchResult]:
    """Convert linkedin_client items to SearchResult list."""
    results = []
    for item in items:
        name = item.get("name", "LinkedIn result")
        url = item.get("url", "")
        headline = item.get("headline", "")
        snippet = item.get("snippet", "")
        content_type = item.get("content_type", "other")

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
    return results


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
    if error := validate_query(query):
        return error

    try:
        items = client.search_linkedin(
            query=query,
            content_type=content_type,
            max_results=max_results,
            depth=depth,
        )

        response = build_search_response(_build_results(items), query)

        if response_format == "markdown":
            return client.format_linkedin_markdown(items, query)

        return response

    except Exception as e:
        logger.exception("LinkedIn search failed for query %r", query)
        return format_error("LinkedIn search failed", str(e))


__all__ = ["linkedin_search_tool", "client"]
