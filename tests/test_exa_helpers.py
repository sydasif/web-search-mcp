"""Offline unit tests for Exa search helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from web_search_mcp.search.exa import _region_to_user_location, _time_range_to_dates


class TestTimeRangeToDates:
    """Test _time_range_to_dates conversion."""

    def test_none_returns_none_pair(self) -> None:
        assert _time_range_to_dates(None) == (None, None)

    def test_invalid_range_returns_none_pair(self) -> None:
        assert _time_range_to_dates("invalid") == (None, None)
        assert _time_range_to_dates("") == (None, None)
        assert _time_range_to_dates("X") == (None, None)

    @pytest.mark.parametrize("code,expected_days", [
        ("d", 1),
        ("w", 7),
        ("m", 30),
        ("y", 365),
    ])
    def test_valid_ranges_return_iso_dates(self, code: str, expected_days: int) -> None:
        start, end = _time_range_to_dates(code)
        assert start is not None
        assert end is not None
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        diff = end_dt - start_dt
        assert diff == timedelta(days=expected_days)
        assert "T" in start
        assert "T" in end
        assert start.endswith(".000Z")
        assert end.endswith(".000Z")


class TestRegionToUserLocation:
    """Test _region_to_user_location conversion."""

    def test_none_returns_none(self) -> None:
        assert _region_to_user_location(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _region_to_user_location("") is None

    def test_us_en_returns_us(self) -> None:
        assert _region_to_user_location("us-en") == "US"

    def test_uk_returns_gb(self) -> None:
        assert _region_to_user_location("uk") == "GB"
        assert _region_to_user_location("uk-en") == "GB"

    def test_fr_returns_fr(self) -> None:
        assert _region_to_user_location("fr") == "FR"
        assert _region_to_user_location("fr-en") == "FR"

    def test_de_returns_de(self) -> None:
        assert _region_to_user_location("de") == "DE"

    def test_lowercased_before_exception_map(self) -> None:
        assert _region_to_user_location("UK") == "GB"

    def test_unknown_region_lowercased(self) -> None:
        assert _region_to_user_location("jp") == "JP"
