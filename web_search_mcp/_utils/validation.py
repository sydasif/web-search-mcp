"""Input validation and sanitization helpers."""

from __future__ import annotations

from .errors import ValidationError


def validate_query(query: str) -> str:
    """Validate search query string."""
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty.")

    cleaned = query.strip()
    if len(cleaned) > 1000:
        raise ValidationError("Search query is too long (maximum 1000 characters).")

    return cleaned


def validate_max_results(max_results: int, min_val: int = 1, max_val: int = 50) -> int:
    """Validate max_results parameter bounds."""
    if not isinstance(max_results, int):
        try:
            max_results = int(max_results)
        except (TypeError, ValueError) as err:
            raise ValidationError("max_results must be an integer.") from err

    if not (min_val <= max_results <= max_val):
        raise ValidationError(f"max_results must be between {min_val} and {max_val}.")

    return max_results


def validate_time_range(time_range: str | None) -> str | None:
    """Validate time_range parameter."""
    if time_range is None:
        return None

    allowed = {"d", "w", "m", "y"}
    if time_range not in allowed:
        raise ValidationError(
            f"Invalid time_range {time_range!r}. Must be one of {sorted(allowed)}."
        )

    return time_range
