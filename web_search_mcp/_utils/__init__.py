"""Shared utilities: formatting, scoring, rate limiting, caching, errors, and validation."""

from __future__ import annotations

from .cache import TTLCache, cached, search_cache
from .errors import (
    ConfigurationError,
    FetchError,
    ProviderError,
    RateLimitError,
    SearchError,
    ValidationError,
    handle_errors,
)
from .formatting import (
    format_error,
    format_results_markdown,
    iso_to_date,
    iso_to_epoch,
    truncate_content,
)
from .rate_limiter import AsyncRateLimiter, RateLimiter
from .scoring import compute_relevance, token_overlap_relevance
from .validation import validate_max_results, validate_query, validate_time_range

__all__ = [
    "AsyncRateLimiter",
    "ConfigurationError",
    "FetchError",
    "ProviderError",
    "RateLimitError",
    "RateLimiter",
    "SearchError",
    "TTLCache",
    "ValidationError",
    "cached",
    "compute_relevance",
    "format_error",
    "format_results_markdown",
    "handle_errors",
    "iso_to_date",
    "iso_to_epoch",
    "search_cache",
    "token_overlap_relevance",
    "truncate_content",
    "validate_max_results",
    "validate_query",
    "validate_time_range",
]
