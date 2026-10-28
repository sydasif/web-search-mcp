"""Response models returned by search and fetch operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from .types import SearchType


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    details: str


class SearchResult(BaseModel):
    """A single search result item."""

    title: str | None = None
    href: str | None = None
    url: str | None = None
    body: str | None = None


class SearchResponse(BaseModel):
    """Structured response for search operations."""

    query: str
    search_type: SearchType
    total_results: int
    results: list[SearchResult]
    has_more: bool
    next_page: int | None = None
    error: str | None = None
    details: str | None = None


class PageResponse(BaseModel):
    """Structured response for page extraction."""

    url: str
    length: int
    content: str
    metadata: dict[str, str | None] | None = None
    warning: str | None = None



def items_to_search_response(
    items: list[dict[str, Any]],
    query: str,
    search_type: SearchType = "text",
    *,
    title_key: str = "title",
    url_key: str = "url",
    body_builder: Callable[[dict[str, Any]], str | None] | None = None,
) -> SearchResponse:
    """Convert a list of dict items to SearchResponse using a customizable body builder.

    Args:
        items: List of dicts containing at least title and URL keys.
        query: The search query string.
        search_type: Type of search ('text' or 'news').
        title_key: Dict key for the title field (default 'title').
        url_key: Dict key for the URL field (default 'url').
        body_builder: Optional function(item) -> str for the body field.
            If None, uses title + url as fallback.

    Returns:
        SearchResponse with standardized structure.
    """

    results: list[SearchResult] = []
    for item in items:
        title = item.get(title_key)
        url = item.get(url_key)
        if not title and not url:
            continue

        if body_builder:
            body = body_builder(item)
        else:
            parts = []
            if title:
                parts.append(str(title))
            if url:
                parts.append(str(url))
            body = " ".join(parts) if parts else None

        results.append(
            SearchResult(
                title=title,
                href=url,
                url=url,
                body=body,
            )
        )

    return build_search_response(results, query, search_type=search_type)

def build_search_response(
    results: list[SearchResult],
    query: str,
    search_type: SearchType = "text",
) -> SearchResponse:
    """Build a SearchResponse with standard defaults."""
    return SearchResponse(
        query=query,
        search_type=search_type,
        total_results=len(results),
        results=results,
        has_more=False,
        next_page=None,
    )
