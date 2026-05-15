import pytest
import time
from web_search_mcp.utils import RateLimiter


def test_rate_limiter_basic():
    """Test that rate limiter allows requests within limit."""
    limiter = RateLimiter(requests_per_minute=5)
    start = time.time()
    for _ in range(5):
        limiter.acquire()
    end = time.time()
    assert end - start < 1.0  # Should not wait significantly


def test_rate_limiter_waiting():
    """Test that rate limiter blocks when limit is exceeded."""
    # Use a small window (0.5s) for fast, meaningful verification
    limiter = RateLimiter(requests_per_minute=2, window_seconds=0.5)

    limiter.acquire()  # 1
    limiter.acquire()  # 2

    start = time.time()
    limiter.acquire()  # 3rd request should wait until the 1st one is > 0.5s old
    end = time.time()

    elapsed = end - start
    assert elapsed >= 0.4  # Should have waited roughly the window size


def test_rate_limiter_zero_limit():
    """Test that rate limiter with 0 limit does not block."""
    limiter = RateLimiter(requests_per_minute=0)
    start = time.time()
    limiter.acquire()
    end = time.time()
    assert end - start < 0.1


def test_rate_limiter_negative_rpm():
    """Test that negative RPM raises ValueError."""
    with pytest.raises(ValueError, match="requests_per_minute must be >= 0"):
        RateLimiter(requests_per_minute=-1)


def test_rate_limiter_zero_window():
    """Test that zero window raises ValueError."""
    with pytest.raises(ValueError, match="window_seconds must be > 0"):
        RateLimiter(window_seconds=0)


def test_rate_limiter_negative_window():
    """Test that negative window raises ValueError."""
    with pytest.raises(ValueError, match="window_seconds must be > 0"):
        RateLimiter(window_seconds=-1.0)


def test_rate_limiter_no_wait_needed():
    """Test the branch where no wait is needed despite being at limit."""
    limiter = RateLimiter(requests_per_minute=2, window_seconds=0.2)
    limiter.acquire()
    time.sleep(0.25)  # Let window expire
    limiter.acquire()
    start = time.time()
    limiter.acquire()  # Should not block because window is effectively empty
    end = time.time()
    assert end - start < 0.1
