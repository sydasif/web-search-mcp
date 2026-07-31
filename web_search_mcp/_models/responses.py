"""Response models returned by search and fetch operations."""

from __future__ import annotations

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


def build_search_response(
    results: list[SearchResult],
    query: str,
) -> SearchResponse:
    """Build a SearchResponse with standard defaults."""
    return SearchResponse(
        query=query,
        search_type="text",
        total_results=len(results),
        results=results,
        has_more=False,
        next_page=None,
    )
