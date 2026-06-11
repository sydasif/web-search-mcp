import pytest
import time
import threading
from web_search_mcp.utils import (
    token_overlap_relevance,
    format_error,
    format_auth_error,
    format_empty_query_error,
    format_empty_response_error,
    RateLimiter,
)


def test_token_overlap_relevance_basic():
    """Test basic token overlap relevance functionality."""
    query = "machine learning algorithms"
    text = "algorithms in machine learning are powerful"

    result = token_overlap_relevance(query, text)
    assert 0.0 <= result <= 1.0
    assert result > 0.0  # Should have some overlap


def test_token_overlap_relevance_perfect_match():
    """Test perfect token overlap."""
    query = "python programming"
    text = "python programming concepts and techniques"

    result = token_overlap_relevance(query, text)
    assert result == 1.0  # All tokens from query present in text


def test_token_overlap_relevance_no_match():
    """Test no token overlap."""
    query = "python programming"
    text = "javascript web development"

    result = token_overlap_relevance(query, text)
    assert result == 0.0


def test_token_overlap_relevance_empty_inputs():
    """Test token overlap relevance with empty strings."""
    assert token_overlap_relevance("", "text") == 0.0
    assert token_overlap_relevance("query", "") == 0.0
    assert token_overlap_relevance("", "") == 0.0


def test_token_overlap_relevance_special_characters():
    """Test token overlap relevance with special characters and punctuation."""
    query = "AI & ML: neural networks"
    text = "neural networks in AI and machine learning"

    result = token_overlap_relevance(query, text)
    assert 0.0 <= result <= 1.0


def test_token_overlap_relevance_case_insensitive():
    """Test that token overlap is case-insensitive."""
    query = "Python Programming"
    text = "python programming is great"

    result1 = token_overlap_relevance(query, text)
    result2 = token_overlap_relevance(query.lower(), text.lower())
    assert result1 == result2


def test_token_overlap_relevance_unicode():
    """Test token overlap relevance with Unicode characters."""
    query = "café ☕"
    text = "café ☕ coffee shop"

    result = token_overlap_relevance(query, text)
    assert result == 1.0  # Perfect overlap including Unicode


def test_token_overlap_relevance_partial_tokens():
    """Test token overlap with partial token matching."""
    query = "data science machine learning"
    text = "machine learning and data analysis"

    result = token_overlap_relevance(query, text)
    assert 0.0 < result < 1.0  # Some overlap but not perfect


def test_format_error_basic():
    """Test format_error with basic parameters."""
    error = format_error("Search failed", "Invalid query format")

    assert error.error == "Search failed"
    assert error.details == "Invalid query format"


def test_format_error_empty_details():
    """Test format_error with empty details."""
    error = format_error("Simple error")

    assert error.error == "Simple error"
    assert error.details == "No additional details provided."


def test_format_error_none_details():
    """Test format_error with None details."""
    error = format_error("Simple error", None)

    assert error.error == "Simple error"
    assert error.details == "No additional details provided."


def test_format_error_empty_message():
    """Test format_error with empty message."""
    error = format_error("")

    assert error.error == ""
    assert error.details == "No additional details provided."


def test_format_auth_error():
    """Test format_auth_error returns consistent auth error."""
    error = format_auth_error()

    assert error.error == "Groq API key not configured"
    assert "SEARCH_MCP_GROQ_API_KEY" in error.details
    assert "GROQ_API_KEY" in error.details


def test_format_empty_query_error():
    """Test format_empty_query_error returns consistent empty query error."""
    error = format_empty_query_error()

    assert error.error == "Query cannot be empty"
    assert "non-empty query string" in error.details
    assert "Example:" in error.details


def test_format_empty_response_error():
    """Test format_empty_response_error returns consistent empty content error."""
    # Test with default source
    error = format_empty_response_error()

    assert error.error == "Groq returned empty content"
    assert "rephrasing your query" in error.details

    # Test with custom source
    error = format_empty_response_error("DDG")

    assert error.error == "DDG returned empty content"
    assert "rephrasing your query" in error.details


def test_format_empty_response_error_details():
    """Test format_empty_response_error includes source in error message."""
    error = format_empty_response_error("GitHub")

    assert error.error == "GitHub returned empty content"
    # Details is a generic template that doesn't include the source
    assert "The model produced no response" in error.details
    assert "Try rephrasing" in error.details


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    def test_rate_limiter_basic_limit(self):
        """Test that rate limiter allows requests within limit."""
        limiter = RateLimiter(requests_per_minute=5)
        start = time.time()
        for _ in range(5):
            limiter.acquire()
        end = time.time()
        assert end - start < 1.0  # Should not wait significantly

    def test_rate_limiter_waiting_behavior(self):
        """Test that rate limiter blocks when limit is exceeded."""
        limiter = RateLimiter(requests_per_minute=2, window_seconds=0.5)

        limiter.acquire()  # 1
        limiter.acquire()  # 2

        start = time.time()
        limiter.acquire()  # 3rd request should wait until 1st is > 0.5s old
        end = time.time()

        elapsed = end - start
        assert elapsed >= 0.4  # Should have waited roughly the window size

    def test_rate_limiter_zero_limit(self):
        """Test that rate limiter with 0 limit does not block."""
        limiter = RateLimiter(requests_per_minute=0)
        start = time.time()
        limiter.acquire()
        end = time.time()
        assert end - start < 0.1

    def test_rate_limiter_negative_rpm(self):
        """Test that negative RPM raises ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be >= 0"):
            RateLimiter(requests_per_minute=-1)

    def test_rate_limiter_zero_window(self):
        """Test that zero window raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(window_seconds=0)

    def test_rate_limiter_negative_window(self):
        """Test that negative window raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(window_seconds=-1.0)

    def test_rate_limiter_no_wait_needed(self):
        """Test the branch where no wait is needed despite being at limit."""
        limiter = RateLimiter(requests_per_minute=2, window_seconds=0.2)
        limiter.acquire()
        time.sleep(0.25)  # Let window expire
        limiter.acquire()
        start = time.time()
        limiter.acquire()  # Should not block because window is effectively empty
        end = time.time()
        assert end - start < 0.1

    def test_rate_limiter_concurrent_access(self):
        """Test rate limiter with concurrent access."""
        limiter = RateLimiter(requests_per_minute=10, window_seconds=1.0)
        results = []

        def acquire_and_record():
            limiter.acquire()
            results.append(time.time())

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=acquire_and_record)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5

    def test_rate_limiter_initial_empty_state(self):
        """Test that rate limiter starts with empty request list."""
        limiter = RateLimiter()
        start = time.time()
        limiter.acquire()  # Should not block
        end = time.time()
        assert end - start < 0.1

    def test_rate_limiter_large_window(self):
        """Test rate limiter with large time window."""
        limiter = RateLimiter(requests_per_minute=10, window_seconds=300.0)  # 5 minutes
        start = time.time()
        for _ in range(10):
            limiter.acquire()
        end = time.time()
        assert end - start < 1.0  # Should allow 10 requests instantly

    def test_rate_limiter_acquire_consistency(self):
        """Test that rate limiter maintains consistent state after acquisitions."""
        limiter = RateLimiter(requests_per_minute=3, window_seconds=60.0)

        limiter.acquire()
        limiter.acquire()

        # Get internal state (testing private attribute)
        initial_count = len(limiter.requests)

        # Make another request
        limiter.acquire()

        final_count = len(limiter.requests)
        assert final_count == initial_count + 1

    def test_rate_limiter_removes_old_requests(self):
        """Test that rate limiter removes old requests from window."""
        limiter = RateLimiter(requests_per_minute=5, window_seconds=1.0)

        # Fill the limiter
        for _ in range(5):
            limiter.acquire()

        # Wait for window to expire
        time.sleep(1.1)

        # Should be able to acquire without waiting
        start = time.time()
        limiter.acquire()
        end = time.time()
        assert end - start < 0.1


class TestUtilityFunctionsIntegration:
    """Integration tests for utility functions."""

    def test_token_overlap_with_error_formatting(self):
        """Test that token overlap and error formatting work together."""
        query = "test"
        text = "different text"

        overlap = token_overlap_relevance(query, text)
        error = format_error("Low relevance detected", f"Overlap score: {overlap:.2f}")

        assert overlap == 0.0
        assert "Low relevance detected" in error.error
        assert "Overlap score: 0.00" in error.details

    def test_rate_limiter_with_error_formatting(self):
        """Test rate limiting integrated with error formatting."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=0.5)

        # Use up the limit
        limiter.acquire()

        # Try again, should wait
        start = time.time()
        limiter.acquire()
        end = time.time()

        assert end - start >= 0.4

        # Create error with timing info
        error = format_error("Rate limit exceeded", f"Waited {(end - start):.2f} seconds")
        assert "Rate limit exceeded" in error.error
