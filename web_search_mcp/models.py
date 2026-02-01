from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class SearchRequest(BaseModel):
    query: str
    search_type: Literal["text", "news"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: str = "moderate"
    page: int = 1
    backend: str = "auto"
    # Catch-all for extra filters
    filters: dict[str, Any] = {}


class FetchPageRequest(BaseModel):
    url: HttpUrl
    output_format: Literal["text", "markdown", "json"] = "text"
    include_metadata: bool = False
    include_tables: bool = False
    include_comments: bool = False
    include_images: bool = False
    deduplicate: bool = True
    max_length: int = Field(default=15000, ge=100, le=50000)
    timeout: int = Field(default=30, ge=5, le=120)
