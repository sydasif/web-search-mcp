"""Tests for date-window utilities."""

from __future__ import annotations

from datetime import date

from web_search_mcp._utils.dates import time_range_to_date_window, time_range_to_dates


class TestTimeRangeToDateWindow:
    """Tests for time_range_to_date_window."""

    def test_none_returns_default_window(self) -> None:
        """None time_range returns full default window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window(None, today=ref)
        assert from_date == "2000-01-01"
        assert to_date == "2025-06-15"

    def test_d_returns_1_day_window(self) -> None:
        """'d' returns 1-day window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window("d", today=ref)
        assert from_date == "2025-06-14"
        assert to_date == "2025-06-15"

    def test_w_returns_1_week_window(self) -> None:
        """'w' returns 1-week window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window("w", today=ref)
        assert from_date == "2025-06-08"
        assert to_date == "2025-06-15"

    def test_m_returns_4_week_window(self) -> None:
        """'m' returns 4-week window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window("m", today=ref)
        assert from_date == "2025-05-18"
        assert to_date == "2025-06-15"

    def test_y_returns_52_week_window(self) -> None:
        """'y' returns 52-week window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window("y", today=ref)
        assert from_date == "2024-06-16"
        assert to_date == "2025-06-15"

    def test_custom_default_from(self) -> None:
        """Custom default_from overrides the fallback."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window(None, today=ref, default_from="2020-01-01")
        assert from_date == "2020-01-01"
        assert to_date == "2025-06-15"

    def test_unknown_time_range_returns_default(self) -> None:
        """Unknown time_range falls back to default window."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_date_window("x", today=ref)
        assert from_date == "2000-01-01"
        assert to_date == "2025-06-15"


class TestTimeRangeToDates:
    """Tests for time_range_to_dates (Exa-compatible, None for unbounded)."""

    def test_none_returns_none_none(self) -> None:
        """None time_range returns (None, None)."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates(None, today=ref)
        assert from_date is None
        assert to_date is None

    def test_d_returns_bounded_dates(self) -> None:
        """'d' returns bounded start/end."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates("d", today=ref)
        assert from_date == "2025-06-14"
        assert to_date == "2025-06-15"

    def test_w_returns_bounded_dates(self) -> None:
        """'w' returns bounded start/end."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates("w", today=ref)
        assert from_date == "2025-06-08"
        assert to_date == "2025-06-15"

    def test_m_returns_bounded_dates(self) -> None:
        """'m' returns bounded start/end."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates("m", today=ref)
        assert from_date == "2025-05-18"
        assert to_date == "2025-06-15"

    def test_y_returns_bounded_dates(self) -> None:
        """'y' returns bounded start/end."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates("y", today=ref)
        assert from_date == "2024-06-16"
        assert to_date == "2025-06-15"

    def test_unknown_time_range_returns_none_none(self) -> None:
        """Unknown time_range returns (None, None)."""
        ref = date(2025, 6, 15)
        from_date, to_date = time_range_to_dates("x", today=ref)
        assert from_date is None
        assert to_date is None
