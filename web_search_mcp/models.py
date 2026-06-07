from typing import Literal
from pydantic import BaseModel, Field


FetchOutputFormat = Literal["csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"]


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
    search_type: Literal["text", "news"]
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


class SearchRequest(BaseModel):
    """Request schema for web and news searches.

    Attributes:
        query: The search query string.
        search_type: The type of search to perform ('text' or 'news'). Defaults to 'text'.
        max_results: Maximum number of results to return. Must be >= 1. Defaults to 5.
        time_range: Time filter for results (e.g., 'd', 'w', 'm', 'y').
        region: Geographic region for search (e.g., 'us-en').
        safesearch: Safe search level ('moderate', 'off', 'on'). Defaults to 'moderate'.
        page: Page number for pagination. Must be >= 1. Defaults to 1.
        backend: Search backend to use ('auto', 'legacy', 'api'). Defaults to 'auto'.
        response_format: Desired response format ('json', 'markdown'). Defaults to 'markdown'.
    """

    query: str
    search_type: Literal["text", "news"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: Literal["moderate", "off", "on"] = "moderate"
    page: int = Field(default=1, ge=1)
    backend: Literal["auto", "legacy", "api"] = "auto"
    response_format: Literal["json", "markdown"] = "markdown"
