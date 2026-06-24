"""Error and markdown formatting helpers."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
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


def truncate_content(text: str, env_var: str, default: int = 30000) -> str:
    """Truncate text to a length specified by an environment variable.

    Reads *env_var* for a max length. Falls back to *default* if the
    variable is missing or unparseable. Appends *Truncated.* when cut.
    Returns the original text unchanged if it is short enough.
    """
    raw = os.environ.get(env_var, str(default))
    try:
        max_chars = int(raw)
    except (TypeError, ValueError):
        max_chars = default
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n\n_Truncated._\n"
    return text


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


def iso_to_date(value: str | None) -> str | None:
    """Parse an ISO-8601 timestamp to YYYY-MM-DD."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return None


def iso_to_epoch(value: str | None) -> float | None:
    """Parse an ISO-8601 timestamp to a Unix epoch float."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None
