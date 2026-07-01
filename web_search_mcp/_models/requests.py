"""Request models for search operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .types import ResponseFormat, SearchType

Provider = Literal["auto", "ddg", "exa"]


class SearchRequest(BaseModel):
    """Request schema for web and news searches.

    Attributes:
        query: The search query string.
        search_type: The type of search to perform ('text' or 'news'). Defaults to 'text'.
        max_results: Maximum number of results to return. Must be >= 1. Defaults to 5.
        time_range: Time filter for results (e.g., 'd', 'w', 'm', 'y').
        region: Geographic region (e.g. 'us-en', 'uk-en'). DDG: passed directly.
            Exa: converts to two-letter ISO country code (user_location).
        provider: Search provider to use ('auto', 'ddg', 'exa'). Defaults to 'auto'.
        response_format: Desired response format ('json', 'markdown'). Defaults to 'markdown'.

    """

    query: str
    search_type: SearchType = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    provider: Provider = "auto"
    response_format: ResponseFormat = "markdown"
