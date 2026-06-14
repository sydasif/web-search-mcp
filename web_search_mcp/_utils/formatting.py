"""Error and markdown formatting helpers."""

from collections.abc import Callable
from typing import Any

from .._models.responses import ErrorResponse


def format_error(message: str, details: str | None = None) -> ErrorResponse:
    """Creates a unified error response.

    Args:
        message: A concise summary of the error with suggested next step.
        details: Additional details or exception messages. Defaults to None.

    Returns:
        An ErrorResponse containing the error message and details.

    """
    return ErrorResponse(
        error=message,
        details=details or "No additional details provided.",
    )


def format_auth_error() -> ErrorResponse:
    """Returns a consistent authentication error."""
    return ErrorResponse(
        error="Groq API key not configured",
        details="Set SEARCH_MCP_GROQ_API_KEY in your MCP config or environment.",
    )


def format_empty_query_error() -> ErrorResponse:
    """Returns a consistent empty-query error."""
    return ErrorResponse(
        error="Query cannot be empty",
        details="Provide a non-empty query string. Example: 'latest AI research papers June 2026'",
    )


def format_empty_response_error(source: str = "Groq") -> ErrorResponse:
    """Returns a consistent empty-content error."""
    return ErrorResponse(
        error=f"{source} returned empty content",
        details="The model produced no response. Try rephrasing your query with more specific detail, or switch to a different tool (e.g. web_search for DDG results, groq_search for AI-powered research).",
    )


def format_results_markdown(
    items: list[dict[str, Any]],
    query: str,
    platform: str,
    item_label: str = "results",
    format_item: Callable[[dict[str, Any], int], list[str]] | None = None,
) -> str:
    """Build a markdown results list shared across platform tools.

    Produces:
        # {Platform} Results for '{query}'
        Found {N} {item_label}.

        1. **[Title](url)**
           ...metadata lines from format_item...

        2. **[Title](url)**
           ...
    """
    if not items:
        return f"No {platform} results found for '{query}'."
    lines: list[str] = [
        f"# {platform} Results for '{query}'",
        f"Found {len(items)} {item_label}.",
        "",
    ]
    if format_item:
        for i, item in enumerate(items, 1):
            lines.extend(format_item(item, i))
            lines.append("")
    return "\n".join(lines)
