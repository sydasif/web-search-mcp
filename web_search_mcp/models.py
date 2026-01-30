from typing import Any, List

from pydantic import BaseModel, Field


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
