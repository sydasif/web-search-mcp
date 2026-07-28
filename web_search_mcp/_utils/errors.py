"""Standardized exception hierarchy and error handling decorators."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from .._models.responses import ErrorResponse
from .formatting import format_error

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SearchError(Exception):
    """Base exception for all web-search-mcp errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class RateLimitError(SearchError):
    """Raised when rate limit is exceeded."""


class ValidationError(SearchError):
    """Raised when input validation fails."""


class ProviderError(SearchError):
    """Raised when an external search provider fails."""


class FetchError(SearchError):
    """Raised when fetching a page or resource fails."""


class ConfigurationError(SearchError):
    """Raised when configuration is invalid or missing."""


def handle_errors(
    context: str = "operation",
) -> Callable[[Callable[..., T]], Callable[..., T | ErrorResponse]]:
    """Decorator to catch SearchErrors and unexpected exceptions, returning ErrorResponse."""

    def decorator(func: Callable[..., T]) -> Callable[..., T | ErrorResponse]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | ErrorResponse:
            try:
                return func(*args, **kwargs)
            except SearchError as e:
                logger.error(
                    "%s failed with SearchError: %s (details: %s)", context, e.message, e.details
                )
                return format_error(e.message, e.details)
            except ValueError as e:
                logger.error("%s failed with ValueError: %s", context, e)
                return format_error(f"Invalid input or parameter in {context}.", str(e))
            except Exception as e:
                logger.exception("Unexpected error in %s: %s", context, e)
                return format_error(f"An unexpected error occurred during {context}.", str(e))

        return wrapper

    return decorator
