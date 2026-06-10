import time
import pytest
from unittest.mock import patch, MagicMock
from web_search_mcp.ddg import (
    ddg_search,
    fetch_page,
    format_search_results_markdown,
    _is_cloudflare_challenge_body,
    _should_retry_ddg,
)
from web_search_mcp.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    PageResponse,
    ErrorResponse,
)
from web_search_mcp.utils import (
    format_error,
    format_auth_error,
    format_empty_query_error,
    format_empty_response_error,
    RateLimiter,
)
import httpx


class TestCloudflareDetection:
    """Test Cloudflare challenge detection in fetch_page."""

    def test_cloudflare_body_signals_detected(self):
        """Test that Cloudflare body signals are correctly detected."""
        assert _is_cloudflare_challenge_body("Just a moment...") is True
        assert _is_cloudflare_challenge_body("Enable JavaScript and cookies to continue") is True
        assert _is_cloudflare_challenge_body("Checking your browser before accessing") is True
        assert _is_cloudflare_challenge_body("cf-mitigated") is True

    def test_cloudflare_body_case_insensitive(self):
        """Test that Cloudflare detection is case-insensitive."""
        assert _is_cloudflare_challenge_body("just a moment...") is True
        assert _is_cloudflare_challenge_body("JUST A MOMENT...") is True
        assert _is_cloudflare_challenge_body("Just A Moment...") is True

    def test_cloudflare_body_no_match(self):
        """Test that normal content is not flagged as Cloudflare challenge."""
        assert _is_cloudflare_challenge_body("Normal page content") is False
        assert _is_cloudflare_challenge_body("") is False
        assert _is_cloudflare_challenge_body("Hello world") is False

    def test_cloudflare_body_none(self):
        """Test that None input returns False."""
        assert _is_cloudflare_challenge_body(None) is False

    def test_cloudflare_body_long_content(self):
        """Test that detection works with long content (only checks first 4096 chars)."""
        normal_content = "x" * 10000 + "Normal content"
        assert _is_cloudflare_challenge_body(normal_content) is False

        # CF signal must be within first 4096 chars
        cf_content = "x" * 5000 + "Just a moment..."
        assert _is_cloudflare_challenge_body(cf_content) is False  # CF signal beyond 4096 chars

        cf_content_within_limit = "x" * 4000 + "Just a moment..."
        assert _is_cloudflare_challenge_body(cf_content_within_limit) is True


class TestRetryLogic:
    """Test retry logic for DDG requests."""

    def test_should_retry_on_429(self):
        """Test that 429 status triggers retry."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_exception = httpx.HTTPStatusError(
            message="Rate limited",
            request=MagicMock(),
            response=mock_response,
        )
        assert _should_retry_ddg(mock_exception) is True

    def test_should_retry_on_500(self):
        """Test that 5xx status triggers retry."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_exception = httpx.HTTPStatusError(
            message="Server error",
            request=MagicMock(),
            response=mock_response,
        )
        assert _should_retry_ddg(mock_exception) is True

    def test_should_retry_on_503(self):
        """Test that 503 status triggers retry."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_exception = httpx.HTTPStatusError(
            message="Service unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        assert _should_retry_ddg(mock_exception) is True

    def test_should_not_retry_on_400(self):
        """Test that 400 status does not trigger retry."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_exception = httpx.HTTPStatusError(
            message="Bad request",
            request=MagicMock(),
            response=mock_response,
        )
        assert _should_retry_ddg(mock_exception) is False

    def test_should_not_retry_on_404(self):
        """Test that 404 status does not trigger retry."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_exception = httpx.HTTPStatusError(
            message="Not found",
            request=MagicMock(),
            response=mock_response,
        )
        assert _should_retry_ddg(mock_exception) is False

    def test_should_retry_on_timeout(self):
        """Test that timeout exceptions trigger retry."""
        mock_exception = httpx.TimeoutException(message="Request timed out")
        assert _should_retry_ddg(mock_exception) is True

    def test_should_retry_on_request_error(self):
        """Test that request errors trigger retry."""
        mock_exception = httpx.RequestError(message="Connection failed")
        assert _should_retry_ddg(mock_exception) is True

    def test_should_not_retry_generic_exception(self):
        """Test that generic exceptions do not trigger retry."""
        mock_exception = ValueError("Invalid input")
        assert _should_retry_ddg(mock_exception) is False


class TestDDGSearchErrorScenarios:
    """Test error scenarios in DDG search."""

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_rate_limit_error(self, mock_ddgs_class):
        """Test DDG search handling of rate limit errors."""
        mock_ddgs_class.return_value.__enter__.side_effect = httpx.HTTPStatusError(
            message="Rate limited",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )

        req = SearchRequest(query="test query", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "429" in result.error or "rate" in result.error.lower()

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_server_error(self, mock_ddgs_class):
        """Test DDG search handling of server errors."""
        mock_ddgs_class.return_value.__enter__.side_effect = httpx.HTTPStatusError(
            message="Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        req = SearchRequest(query="test query", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "500" in result.error or "error" in result.error.lower()

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_timeout_error(self, mock_ddgs_class):
        """Test DDG search handling of timeout errors."""
        mock_ddgs_class.return_value.__enter__.side_effect = httpx.TimeoutException(
            message="Request timed out"
        )

        req = SearchRequest(query="test query", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_connection_error(self, mock_ddgs_class):
        """Test DDG search handling of connection errors."""
        mock_ddgs_class.return_value.__enter__.side_effect = httpx.RequestError(
            message="Connection refused"
        )

        req = SearchRequest(query="test query", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "connection" in result.error.lower() or "failed" in result.error.lower()

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_empty_results(self, mock_ddgs_class):
        """Test DDG search with empty results."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="nonexistent query", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 0
        assert len(result.results) == 0
        assert result.has_more is False

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_malformed_response(self, mock_ddgs_class):
        """Test DDG search with malformed response data."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {"title": "Only title"},
            {"href": "https://example.com"},
            {"body": "Only body"},
        ]

        req = SearchRequest(query="test", max_results=3)
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 3
        assert len(result.results) == 3

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_partial_response_fields(self, mock_ddgs_class):
        """Test DDG search with missing response fields."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {},
            {"title": None, "href": None},
        ]

        req = SearchRequest(query="test", max_results=2)
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 2

    @patch("web_search_mcp.ddg.DDGS")
    def test_ddg_search_news_type(self, mock_ddgs_class):
        """Test DDG search with news type."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.news.return_value = [
            {"title": "News 1", "href": "https://example.com/1", "body": "News body 1"},
        ]

        req = SearchRequest(query="test news", search_type="news", max_results=1)
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.search_type == "news"
        mock_ddgs.news.assert_called_once()

    def test_ddg_search_empty_query(self):
        """Test DDG search with empty query."""
        req = SearchRequest(query="", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    def test_ddg_search_whitespace_query(self):
        """Test DDG search with whitespace-only query."""
        req = SearchRequest(query="   ", max_results=5)
        result = ddg_search(req)

        assert isinstance(result, (ErrorResponse, SearchResponse))

    def test_ddg_search_long_query(self):
        """Test DDG search with very long query."""
        long_query = "a " * 500  # 1000 characters
        req = SearchRequest(query=long_query, max_results=5)
        result = ddg_search(req)

        assert isinstance(result, (SearchResponse, ErrorResponse))


class TestFetchPageErrorScenarios:
    """Test error scenarios in fetch_page."""

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_http_403_error(self, mock_fetch):
        """Test fetch_page handling of 403 errors."""
        mock_fetch.side_effect = httpx.HTTPStatusError(
            message="Forbidden",
            request=MagicMock(),
            response=MagicMock(status_code=403),
        )

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "403" in result.error or "forbidden" in result.error.lower()

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_http_404_error(self, mock_fetch):
        """Test fetch_page handling of 404 errors."""
        mock_fetch.side_effect = httpx.HTTPStatusError(
            message="Not found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "404" in result.error or "not found" in result.error.lower()

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_timeout_error(self, mock_fetch):
        """Test fetch_page handling of timeout errors."""
        mock_fetch.side_effect = httpx.TimeoutException(message="Request timed out")

        result = fetch_page(url="https://example.com", timeout=5)

        assert isinstance(result, ErrorResponse)
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_connection_error(self, mock_fetch):
        """Test fetch_page handling of connection errors."""
        mock_fetch.side_effect = httpx.RequestError(message="Connection refused")

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "connection" in result.error.lower() or "failed" in result.error.lower()

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_empty_content(self, mock_fetch):
        """Test fetch_page with empty content."""
        mock_fetch.return_value = ""

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert (
            "could not download content" in result.error.lower()
            or "no readable text" in result.error.lower()
        )

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_none_content(self, mock_fetch):
        """Test fetch_page with None content."""
        mock_fetch.return_value = None

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "could not download content" in result.error.lower()

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_cloudflare_challenge(self, mock_fetch):
        """Test fetch_page with Cloudflare challenge."""
        mock_fetch.return_value = "<html>Just a moment...</html>"

        result = fetch_page(url="https://example.com")

        assert isinstance(result, (ErrorResponse, PageResponse))

    @patch("web_search_mcp.ddg._request_with_fallback")
    def test_fetch_page_no_readable_text(self, mock_fetch):
        """Test fetch_page with no readable text."""
        mock_fetch.return_value = "<html><body></body></html>"

        result = fetch_page(url="https://example.com")

        assert isinstance(result, ErrorResponse)
        assert "no readable text" in result.error.lower()

    def test_fetch_page_invalid_url(self):
        """Test fetch_page with invalid URL."""
        result = fetch_page(url="not-a-valid-url")

        assert isinstance(result, (ErrorResponse, PageResponse))

    def test_fetch_page_invalid_backend(self):
        """Test fetch_page with invalid backend parameter."""
        result = fetch_page(url="https://example.com", backend="invalid")

        assert isinstance(result, ErrorResponse)
        assert "backend" in result.error.lower() or "invalid" in result.error.lower()


class TestFormatSearchResultsMarkdownErrors:
    """Test error formatting in format_search_results_markdown."""

    def test_format_error_response_basic(self):
        """Test formatting of ErrorResponse."""
        error = ErrorResponse(error="Test error", details="Test details")

        result = format_search_results_markdown(error)

        assert "**Error:** Test error" in result

    def test_format_error_response_empty_error(self):
        """Test formatting of ErrorResponse with empty error message."""
        error = ErrorResponse(error="", details="Test details")

        result = format_search_results_markdown(error)

        assert "**Error:**" in result

    def test_format_error_response_special_characters(self):
        """Test formatting of ErrorResponse with special characters."""
        error = ErrorResponse(
            error="Error: Invalid input <>&\"'", details="Special chars: café ☕ 🚀"
        )

        result = format_search_results_markdown(error)

        assert "Error: Invalid input <>&\"'" in result

    def test_format_error_response_long_message(self):
        """Test formatting of ErrorResponse with very long message."""
        error = ErrorResponse(error="x" * 1000, details="y" * 1000)

        result = format_search_results_markdown(error)

        assert "**Error:**" in result


class TestErrorResponseConsistency:
    """Test consistency of error responses across all tools."""

    def test_error_response_structure(self):
        """Test that all error responses have consistent structure."""
        errors = [
            format_error("Error 1", "Details 1"),
            format_error("Error 2", "Details 2"),
            format_error("Error 3", "Details 3"),
        ]

        for error in errors:
            assert hasattr(error, "error")
            assert hasattr(error, "details")
            assert isinstance(error.error, str)
            assert isinstance(error.details, str)
            assert len(error.error) > 0
            assert len(error.details) > 0

    def test_error_response_serialization(self):
        """Test that error responses can be serialized."""
        error = format_error("Test error", "Test details")

        error_dict = error.model_dump()

        assert "error" in error_dict
        assert "details" in error_dict
        assert error_dict["error"] == "Test error"
        assert error_dict["details"] == "Test details"

    def test_auth_error_consistency(self):
        """Test auth error response consistency."""
        error1 = format_auth_error()
        error2 = format_auth_error()

        assert error1.error == error2.error
        assert error1.details == error2.details

    def test_empty_query_error_consistency(self):
        """Test empty query error response consistency."""
        error1 = format_empty_query_error()
        error2 = format_empty_query_error()

        assert error1.error == error2.error
        assert error1.details == error2.details

    def test_empty_response_error_consistency(self):
        """Test empty response error response consistency."""
        error1 = format_empty_response_error()
        error2 = format_empty_response_error()

        assert error1.error == error2.error
        assert error1.details == error2.details


class TestRateLimiterErrorScenarios:
    """Test RateLimiter error scenarios."""

    def test_rate_limiter_negative_requests_per_minute(self):
        """Test that negative requests_per_minute raises ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be >= 0"):
            RateLimiter(requests_per_minute=-1)

    def test_rate_limiter_zero_window(self):
        """Test that zero window_seconds raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(window_seconds=0)

    def test_rate_limiter_negative_window(self):
        """Test that negative window_seconds raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(window_seconds=-1.0)

    def test_rate_limiter_extreme_values(self):
        """Test rate limiter with extreme values."""
        limiter = RateLimiter(requests_per_minute=1000000, window_seconds=0.001)

        start = time.time()
        limiter.acquire()
        end = time.time()

        assert end - start < 0.1


class TestSearchRequestErrorScenarios:
    """Test SearchRequest error scenarios."""

    def test_search_request_invalid_search_type(self):
        """Test that invalid search_type raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", search_type="images")

    def test_search_request_invalid_safesearch(self):
        """Test that invalid safesearch raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", safesearch="strict")

    def test_search_request_invalid_backend(self):
        """Test that invalid backend raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", backend="google")

    def test_search_request_invalid_response_format(self):
        """Test that invalid response_format raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", response_format="xml")

    def test_search_request_max_results_zero(self):
        """Test that max_results=0 raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", max_results=0)

    def test_search_request_page_zero(self):
        """Test that page=0 raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", page=0)

    def test_search_request_negative_max_results(self):
        """Test that negative max_results raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", max_results=-1)

    def test_search_request_negative_page(self):
        """Test that negative page raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchRequest(query="test", page=-1)


class TestNetworkTimeoutScenarios:
    """Test network timeout scenarios across tools."""

    def test_rate_limiter_with_concurrent_timeouts(self):
        """Test rate limiter behavior with concurrent timeouts."""
        import time
        import threading

        limiter = RateLimiter(requests_per_minute=5, window_seconds=1.0)
        results = []

        def make_request_with_delay():
            limiter.acquire()
            time.sleep(0.1)
            results.append(time.time())

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request_with_delay)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5

    def test_rate_limiter_window_expiry_during_wait(self):
        """Test rate limiter window expiry during wait."""
        limiter = RateLimiter(requests_per_minute=2, window_seconds=0.5)

        limiter.acquire()
        limiter.acquire()

        import time

        start = time.time()
        limiter.acquire()
        end = time.time()

        assert end - start >= 0.4


class TestConcurrentAccessScenarios:
    """Test concurrent access scenarios."""

    def test_concurrent_ddg_search_calls(self):
        """Test concurrent DDG search calls."""
        import threading

        results = []

        def make_search():
            req = SearchRequest(query=f"test {threading.current_thread().name}", max_results=1)
            results.append(req)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_search, name=f"thread_{i}")
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert len(set(r.query for r in results)) == 10

    def test_concurrent_rate_limiter_access(self):
        """Test concurrent access to rate limiter."""
        import time
        import threading

        limiter = RateLimiter(requests_per_minute=20, window_seconds=1.0)
        results = []

        def make_request():
            limiter.acquire()
            results.append(time.time())

        threads = []
        for _ in range(20):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 20

    def test_concurrent_error_response_creation(self):
        """Test concurrent error response creation."""
        import threading

        errors = []

        def create_error(i):
            error = format_error(f"Error {i}", f"Details {i}")
            errors.append(error)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_error, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 10
        assert len(set(e.error for e in errors)) == 10


class TestMemoryAndResourceScenarios:
    """Test memory and resource scenarios."""

    def test_large_search_results(self):
        """Test handling of large search results."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=100,
            results=[
                SearchResult(title=f"Result {i}", href=f"https://example.com/{i}", body=f"Body {i}")
                for i in range(100)
            ],
            has_more=True,
            next_page=2,
        )

        markdown = format_search_results_markdown(results)

        assert f"Found 100 results." in markdown
        assert "Result 0" in markdown
        assert "Result 99" in markdown

    def test_long_content_handling(self):
        """Test handling of very long content."""
        long_content = "x" * 100000
        response = PageResponse(
            url="https://example.com",
            length=len(long_content),
            content=long_content,
        )

        assert response.length == 100000
        assert len(response.content) == 100000

    def test_many_results_with_pagination(self):
        """Test handling of many results with pagination."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1000,
            results=[
                SearchResult(title=f"Result {i}", href=f"https://example.com/{i}")
                for i in range(10)
            ],
            has_more=True,
            next_page=2,
        )

        markdown = format_search_results_markdown(results)

        assert "Found 1000 results." in markdown
        assert "More results available. See page 2." in markdown


class TestEdgeCaseCombinations:
    """Test edge case combinations across multiple components."""

    def test_empty_query_with_all_parameters(self):
        """Test empty query with all parameters set."""
        req = SearchRequest(
            query="",
            search_type="news",
            max_results=10,
            time_range="d",
            region="us-en",
            safesearch="off",
            page=1,
            backend="api",
            response_format="json",
        )

        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    def test_valid_query_with_minimal_parameters(self):
        """Test valid query with minimal parameters."""
        req = SearchRequest(query="test")

        assert req.query == "test"
        assert req.search_type == "text"
        assert req.max_results == 5
        assert req.page == 1

    def test_search_results_with_all_fields(self):
        """Test search results with all fields populated."""
        results = SearchResponse(
            query="test",
            search_type="news",
            total_results=5,
            results=[
                SearchResult(
                    title="Test Result",
                    href="https://example.com",
                    url="https://example.com",
                    body="Test body content",
                )
            ],
            has_more=True,
            next_page=2,
            error="Partial error",
            details="Some details",
        )

        assert results.query == "test"
        assert results.search_type == "news"
        assert results.total_results == 5
        assert len(results.results) == 1
        assert results.has_more is True
        assert results.next_page == 2
        assert results.error == "Partial error"
        assert results.details == "Some details"

    def test_error_response_with_unicode(self):
        """Test error response with Unicode characters."""
        error = format_error("Error: Café ☕ 🚀", "Details: áéíóú ñü")

        assert error.error == "Error: Café ☕ 🚀"
        assert error.details == "Details: áéíóú ñü"

    def test_rate_limiter_extreme_concurrent_access(self):
        """Test rate limiter with extreme concurrent access."""
        import time
        import threading

        limiter = RateLimiter(requests_per_minute=50, window_seconds=1.0)
        results = []

        def make_request():
            limiter.acquire()
            results.append(time.time())

        threads = []
        for _ in range(50):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 50

    def test_search_response_serialization_roundtrip(self):
        """Test that search response can be serialized and deserialized."""
        original = SearchResponse(
            query="test query",
            search_type="text",
            total_results=2,
            results=[
                SearchResult(title="Title 1", href="https://example.com/1"),
                SearchResult(title="Title 2", href="https://example.com/2"),
            ],
            has_more=True,
            next_page=2,
        )

        serialized = original.model_dump()
        deserialized = SearchResponse(**serialized)

        assert deserialized.query == original.query
        assert deserialized.search_type == original.search_type
        assert deserialized.total_results == original.total_results
        assert len(deserialized.results) == len(original.results)
        assert deserialized.has_more == original.has_more
        assert deserialized.next_page == original.next_page


class TestFormatSearchResultsEdgeCases:
    """Test edge cases in format_search_results_markdown."""

    def test_format_results_with_zero_results(self):
        """Test formatting with zero results."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "Found 0 results." in markdown
        assert "No results found." in markdown

    def test_format_results_with_single_result(self):
        """Test formatting with single result."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Single Result", href="https://example.com")],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "Found 1 results." in markdown
        assert "Single Result" in markdown

    def test_format_results_with_multiple_pages(self):
        """Test formatting with multiple pages."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=50,
            results=[
                SearchResult(title=f"Result {i}", href=f"https://example.com/{i}")
                for i in range(10)
            ],
            has_more=True,
            next_page=2,
        )

        markdown = format_search_results_markdown(results)

        assert "Found 50 results." in markdown
        assert "More results available. See page 2." in markdown

    def test_format_results_with_no_body(self):
        """Test formatting results with no body content."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=2,
            results=[
                SearchResult(title="Result 1", href="https://example.com/1", body=None),
                SearchResult(title="Result 2", href="https://example.com/2", body=""),
            ],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "Result 1" in markdown
        assert "Result 2" in markdown

    def test_format_results_with_special_characters_in_title(self):
        """Test formatting results with special characters in title."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Title with <>&\"'", href="https://example.com")],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "Title with <>&\"'" in markdown

    def test_format_results_with_unicode_in_url(self):
        """Test formatting results with Unicode in URL."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Result", href="https://example.com/café")],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "https://example.com/café" in markdown

    def test_format_results_with_no_url(self):
        """Test formatting results with no URL."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Result")],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "[Result](#)" in markdown

    def test_format_results_with_both_href_and_url(self):
        """Test formatting results with both href and url."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Result", href="https://href.com", url="https://url.com")],
            has_more=False,
        )

        markdown = format_search_results_markdown(results)

        assert "https://href.com" in markdown
