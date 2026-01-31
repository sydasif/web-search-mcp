from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    search_type: Literal["text", "image", "news", "video", "books"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: str = "moderate"
    page: int = 1
    backend: str = "auto"
    filters: dict[str, Any] = {}


class SearchResult(BaseModel):
    title: str
    url: str
    description: str | None = None


class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: list[Any]  # Using Any since DDG results vary by type
    error: str | None = None


class WeatherRequest(BaseModel):
    latitude: float
    longitude: float
    days: int = Field(default=7, ge=1, le=16)


class WeatherResponse(BaseModel):
    latitude: float
    longitude: float
    timezone: str | None = None
    current: dict | None = None
    daily: dict | None = None
    error: str | None = None
