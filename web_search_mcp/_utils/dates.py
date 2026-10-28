"""Shared date-window utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

_TIME_RANGE_MAP: dict[str, timedelta] = {
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
    "m": timedelta(weeks=4),
    "y": timedelta(weeks=52),
}


def time_range_to_date_window(
    time_range: str | None,
    *,
    today: date | None = None,
    default_from: str = "2000-01-01",
) -> tuple[str, str]:
    """Convert a time_range code into (from_date, to_date) ISO strings.

    Args:
        time_range: One of 'd', 'w', 'm', 'y', or None.
        today: Optional reference date (defaults to UTC today).
        default_from: Fallback start date when time_range is None.

    Returns:
        Tuple of (from_date, to_date) as YYYY-MM-DD strings.
    """
    if today is None:
        today = datetime.now(UTC).date()

    to_date = today.isoformat()
    from_date = default_from

    if time_range:
        delta = _TIME_RANGE_MAP.get(time_range)
        if delta:
            from_date = (today - delta).isoformat()

    return from_date, to_date


def time_range_to_dates(
    time_range: str | None,
    *,
    today: date | None = None,
) -> tuple[str | None, str | None]:
    """Convert time_range to Exa-compatible start_published_date / end_published_date.

    Unlike time_range_to_date_window, returns None for unbounded ends.
    """
    if today is None:
        today = datetime.now(UTC).date()

    if not time_range:
        return None, None

    delta = _TIME_RANGE_MAP.get(time_range)
    if not delta:
        return None, None

    from_date = (today - delta).isoformat()
    return from_date, today.isoformat()
