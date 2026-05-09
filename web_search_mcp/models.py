from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    search_type: Literal["text", "news"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: str = "moderate"
    page: int = 1
    backend: str = "auto"
    filters: dict[str, Any] = {}