"""Offline unit tests for the sliding-window rate limiter."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from web_search_mcp._utils.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """Test constructor validation."""

    def test_negative_requests_per_minute_raises(self) -> None:
        with pytest.raises(ValueError, match="requests_per_minute"):
            RateLimiter(requests_per_minute=-1)

    def test_zero_requests_per_minute_allowed(self) -> None:
        rl = RateLimiter(requests_per_minute=0)
        assert rl.requests_per_minute == 0

    def test_zero_window_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="window_seconds"):
            RateLimiter(window_seconds=0)

    def test_negative_window_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="window_seconds"):
            RateLimiter(window_seconds=-1.0)


class TestRateLimiterAcquire:
    """Test acquire behavior with time manipulation."""

    def test_zero_rpm_returns_immediately(self) -> None:
        rl = RateLimiter(requests_per_minute=0)
        for _ in range(100):
            rl.acquire()

    def test_acquire_under_limit(self) -> None:
        rl = RateLimiter(requests_per_minute=5, window_seconds=60.0)
        for _ in range(5):
            rl.acquire()

    @patch("web_search_mcp._utils.rate_limiter.time.sleep")
    def test_acquire_blocks_when_limit_reached(self, mock_sleep: object) -> None:
        rl = RateLimiter(requests_per_minute=2, window_seconds=60.0)
        rl.acquire()
        rl.acquire()
        # Side effect to stop infinite loop on mocked time
        def stop_loop(*args: object) -> None:
            rl.requests.clear()
        mock_sleep.side_effect = stop_loop
        rl.acquire()
        mock_sleep.assert_called_once()

    def test_window_expiry_allows_new_acquire(self) -> None:
        rl = RateLimiter(requests_per_minute=1, window_seconds=0.01)
        rl.acquire()
        import time
        time.sleep(0.02)
        with patch("web_search_mcp._utils.rate_limiter.time.sleep") as mock_sleep:
            rl.acquire()
            mock_sleep.assert_not_called()