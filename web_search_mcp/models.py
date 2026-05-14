from pydantic import BaseModel, Field
from typing import Literal


class SearchRequest(BaseModel):
    query: str
    search_type: Literal["text", "news"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: Literal["moderate", "off", "on"] = "moderate"
    page: int = Field(default=1, ge=1)
    backend: Literal["auto", "legacy", "api"] = "auto"
    response_format: Literal["json", "markdown"] = "markdown"
