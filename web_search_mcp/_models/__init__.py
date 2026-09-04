"""Shared Pydantic models and type aliases."""

from .requests import SearchRequest
from .responses import (
    ErrorResponse,
    PageResponse,
    SearchResponse,
    SearchResult,
    build_search_response,
)
from .types import Depth, FetchOutputFormat, ResponseFormat, SearchType, SortCriterion

__all__ = [
    "ErrorResponse",
    "FetchOutputFormat",
    "PageResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "Depth",
    "FetchOutputFormat",
    "ResponseFormat",
    "SearchType",
    "SortCriterion",
    "build_search_response",
]
