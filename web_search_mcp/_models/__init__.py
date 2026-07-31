"""Shared Pydantic models and type aliases."""

from .requests import SearchRequest
from .responses import (
    ErrorResponse,
    PageResponse,
    SearchResponse,
    SearchResult,
    build_search_response,
)
from .types import FetchOutputFormat

__all__ = [
    "ErrorResponse",
    "FetchOutputFormat",
    "PageResponse",
    "SearchRequest",
    "SearchResponse",
    "build_search_response",
    "SearchResult",
]
