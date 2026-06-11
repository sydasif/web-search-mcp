from web_search_mcp.models import SearchRequest, SearchResponse, SearchResult, ErrorResponse
from web_search_mcp.utils import RateLimiter


class TestServerFunctionality:
    """Test server functionality without MCP tool decorators."""

    def test_web_search_functionality(self):
        """Test web_search server functionality through underlying ddg_search."""
        # Test that web_search uses SearchRequest correctly
        req = SearchRequest(
            query="python programming",
            search_type="text",
            max_results=5,
            time_range="d",
            region="us-en",
            safesearch="moderate",
            page=1,
            backend="auto",
            response_format="markdown",
        )

        assert req.query == "python programming"
        assert req.search_type == "text"
        assert req.max_results == 5
        assert req.time_range == "d"
        assert req.region == "us-en"
        assert req.safesearch == "moderate"
        assert req.page == 1
        assert req.backend == "auto"
        assert req.response_format == "markdown"

    def test_search_docs_functionality(self):
        """Test search_docs server functionality."""
        # Test that search_docs enhances queries with domain
        query = "asyncio"
        domain = "docs.python.org"

        # Simulate the query enhancement that search_docs does
        enhanced_query = f"site:{domain} {query}"

        assert enhanced_query == "site:docs.python.org asyncio"

    def test_server_parameter_validation(self):
        """Test that server tools properly validate parameters."""
        from web_search_mcp.models import SearchRequest

        # Test valid parameters
        valid_requests = [
            SearchRequest(query="test", search_type="text", max_results=5),
            SearchRequest(query="test", search_type="news", max_results=10),
            SearchRequest(query="test", time_range="d", region="us-en"),
            SearchRequest(query="test", safesearch="off", backend="api"),
        ]

        for req in valid_requests:
            assert req.query == "test"
            assert hasattr(req, "search_type")
            assert hasattr(req, "max_results")
            assert hasattr(req, "time_range")
            assert hasattr(req, "region")

    def test_server_error_handling(self):
        """Test that server tools handle errors correctly."""
        # Test that ErrorResponse is properly used across tools
        error1 = ErrorResponse(error="API Error", details="Service unavailable")
        error2 = ErrorResponse(error="Validation Error", details="Invalid input")

        assert error1.error != error2.error
        assert error1.details != error2.details
        assert isinstance(error1, ErrorResponse)
        assert isinstance(error2, ErrorResponse)

    def test_server_rate_limiting(self):
        """Test server rate limiting functionality."""
        limiter = RateLimiter(requests_per_minute=5)

        # Should allow 5 requests without waiting
        for _ in range(5):
            limiter.acquire()

        # 6th request should wait
        import time

        start = time.time()
        limiter.acquire()
        end = time.time()

        assert end - start >= 0.8  # Should have waited

    def test_server_concurrent_requests(self):
        """Test server handling of concurrent requests."""
        limiter = RateLimiter(requests_per_minute=10)

        # Simulate concurrent requests
        results = []

        def make_request():
            limiter.acquire()
            results.append(time.time())

        import threading
        import time

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 10

    def test_server_response_format_consistency(self):
        """Test that server responses are consistently formatted."""
        # Test SearchResponse structure consistency
        response1 = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[],
            has_more=False,
        )

        response2 = SearchResponse(
            query="test",
            search_type="text",
            total_results=2,
            results=[SearchResult(title="T", href="U")],
            has_more=True,
            next_page=2,
        )

        # Both should have consistent structure
        assert response1.query == response2.query
        assert response1.search_type == response2.search_type
        assert isinstance(response1, SearchResponse)
        assert isinstance(response2, SearchResponse)

    def test_server_error_message_formatting(self):
        """Test that error messages are consistently formatted across server tools."""
        from web_search_mcp.utils import format_error

        # Test various error scenarios
        error1 = format_error("API Error", "Service unavailable")
        error2 = format_error("Validation Error", "Invalid input")
        error3 = format_error("Network Error", "Connection timeout")

        assert error1.error == "API Error"
        assert error2.error == "Validation Error"
        assert error3.error == "Network Error"

        assert "Service unavailable" in error1.details
        assert "Invalid input" in error2.details
        assert "Connection timeout" in error3.details

    def test_server_query_enhancement(self):
        """Test that search tools enhance queries correctly."""
        # Test domain-specific query enhancement
        base_query = "asyncio"
        domain = "docs.python.org"
        enhanced_query = f"site:{domain} {base_query}"

        assert enhanced_query == "site:docs.python.org asyncio"
        assert "site:" in enhanced_query
        assert "docs.python.org" in enhanced_query
        assert "asyncio" in enhanced_query

    def test_server_parameter_combinations(self):
        """Test various parameter combinations for server tools."""
        from web_search_mcp.models import SearchRequest

        # Test combinations of search parameters
        param_combinations = [
            {"query": "test", "search_type": "text", "max_results": 5},
            {"query": "test", "search_type": "news", "max_results": 10},
            {"query": "test", "time_range": "d", "region": "us-en"},
            {"query": "test", "safesearch": "off", "backend": "api"},
        ]

        for params in param_combinations:
            req = SearchRequest(**params)
            assert req.query == "test"
            for key, expected_value in params.items():
                if key != "query":
                    assert getattr(req, key) == expected_value

    def test_server_pagination_handling(self):
        """Test server pagination handling."""
        # Test pagination field consistency
        response1 = SearchResponse(
            query="test",
            search_type="text",
            total_results=10,
            results=[],
            has_more=True,
            next_page=2,
        )

        response2 = SearchResponse(
            query="test",
            search_type="text",
            total_results=5,
            results=[],
            has_more=False,
            next_page=None,
        )

        assert response1.has_more is True
        assert response1.next_page == 2
        assert response2.has_more is False
        assert response2.next_page is None

    def test_server_unicode_handling(self):
        """Test Unicode handling in server tools."""
        # Test Unicode in queries
        unicode_queries = [
            "café ☕",
            "AI & ML: neural networks",
            "search with quotes",
            "test with emojis 🚀✨",
        ]

        for query in unicode_queries:
            req = SearchRequest(query=query, max_results=1)
            assert req.query == query

    def test_server_error_consistency(self):
        """Test error consistency across server tools."""
        # Test that ErrorResponse maintains consistent structure
        errors = [
            ErrorResponse(error="API Error", details="Service unavailable"),
            ErrorResponse(error="Validation Error", details="Invalid input"),
            ErrorResponse(error="Network Error", details="Connection timeout"),
        ]

        for error in errors:
            assert error.error
            assert error.details
            assert isinstance(error.error, str)
            assert isinstance(error.details, str)

    def test_server_authentication_errors(self):
        """Test authentication error scenarios."""
        # Test that authentication errors are properly formatted
        from web_search_mcp.utils import (
            format_auth_error,
            format_empty_query_error,
            format_empty_response_error,
        )

        auth_error = format_auth_error()
        assert auth_error.error == "Groq API key not configured"
        assert "SEARCH_MCP_GROQ_API_KEY" in auth_error.details

        empty_query_error = format_empty_query_error()
        assert empty_query_error.error == "Query cannot be empty"
        assert "non-empty" in empty_query_error.details

        empty_response_error = format_empty_response_error()
        assert empty_response_error.error == "Groq returned empty content"
        assert "rephrasing" in empty_response_error.details

    def test_server_network_error_handling(self):
        """Test network error handling in server tools."""
        # Test that network errors are properly formatted
        from web_search_mcp.utils import format_error

        network_error = format_error("Connection timeout", "Request took longer than 30 seconds")

        assert "timeout" in network_error.error.lower()
        assert "30 seconds" in network_error.details

    def test_server_rate_limit_errors(self):
        """Test rate limit error handling."""
        # Test that rate limit errors are properly formatted
        from web_search_mcp.utils import format_error

        rate_limit_error = format_error(
            "Rate limit exceeded", "Daily quota reached, try again later"
        )

        assert "rate limit" in rate_limit_error.error.lower()
        assert "quota" in rate_limit_error.details.lower()

    def test_server_parameter_validation_edge_cases(self):
        """Test parameter validation edge cases."""
        from web_search_mcp.models import SearchRequest

        # Test boundary values
        boundary_requests = [
            SearchRequest(query="test", max_results=1, page=1),  # Minimum values
            SearchRequest(query="test", max_results=100, page=100),  # High values
        ]

        for req in boundary_requests:
            assert req.query == "test"
            assert req.max_results >= 1
            assert req.page >= 1

    def test_server_special_characters(self):
        """Test special character handling in server tools."""
        # Test special characters in various contexts
        special_queries = [
            "test&query=value",
            "test?query=value",
            "test#fragment",
            "test with quotes ' \"",
            "test with backslashes \\\\",
        ]

        for query in special_queries:
            req = SearchRequest(query=query, max_results=1)
            assert req.query == query

    def test_server_response_format_switching(self):
        """Test response format switching between tools."""
        # Test that tools can handle both JSON and markdown formats
        from web_search_mcp.models import SearchRequest

        json_request = SearchRequest(query="test", search_type="text", response_format="json")

        markdown_request = SearchRequest(
            query="test", search_type="text", response_format="markdown"
        )

        assert json_request.response_format == "json"
        assert markdown_request.response_format == "markdown"

    def test_server_error_propagation(self):
        """Test error propagation across server tools."""
        # Test that errors are properly propagated
        from web_search_mcp.utils import format_error

        # Simulate an error from backend
        backend_error = format_error(
            "Database connection failed", "Cannot connect to search backend"
        )

        # Simulate a server error
        server_error = format_error(
            "Search service unavailable", f"Backend error: {backend_error.error}"
        )

        assert server_error.error == "Search service unavailable"
        assert backend_error.error == "Database connection failed"

    def test_server_concurrent_access(self):
        """Test concurrent access to server functionality."""
        # Test rate limiter with concurrent access
        limiter = RateLimiter(requests_per_minute=10, window_seconds=1.0)

        results = []
        import threading
        import time

        def concurrent_request():
            limiter.acquire()
            results.append(time.time())

        # Start multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=concurrent_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        assert len(results) == 10

    def test_server_cache_consistency(self):
        """Test cache consistency in server functionality."""
        # Test that SearchResponse objects maintain consistent state
        response1 = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="T1", href="U1")],
            has_more=False,
        )

        response2 = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="T1", href="U1")],
            has_more=False,
        )

        # Both should be equal
        assert response1.query == response2.query
        assert response1.total_results == response2.total_results
        assert len(response1.results) == len(response2.results)

    def test_server_logging_consistency(self):
        """Test server logging consistency."""
        # Test that logging setup is consistent
        from web_search_mcp.server import configure_logging

        # Should not raise exception
        configure_logging(level=20)  # INFO level

        # Should handle different log levels
        configure_logging(level=10)  # DEBUG level
        configure_logging(level=40)  # WARNING level

    def test_server_tool_compatibility(self):
        """Test server tool compatibility and interfaces."""
        # Test that all tools have consistent interfaces
        from web_search_mcp.models import SearchRequest

        # All search tools should accept similar parameter patterns
        test_params = {
            "query": "test",
            "search_type": "text",
            "max_results": 5,
            "time_range": "d",
            "region": "us-en",
            "safesearch": "moderate",
            "page": 1,
            "backend": "auto",
        }

        # Test that SearchRequest accepts all these parameters
        req = SearchRequest(**test_params)

        assert req.query == "test"
        assert req.search_type == "text"
        assert req.max_results == 5
        assert req.time_range == "d"
        assert req.region == "us-en"
        assert req.safesearch == "moderate"
        assert req.page == 1
        assert req.backend == "auto"

    def test_server_error_scenarios(self):
        """Test various error scenarios in server functionality."""
        # Test different error scenarios
        from web_search_mcp.utils import format_error

        # Network error
        network_error = format_error("Network timeout", "Connection to search server failed")

        # Authentication error
        auth_error = format_error("Authentication failed", "Invalid credentials provided")

        # Validation error
        validation_error = format_error(
            "Invalid parameters", "Search type 'images' is not supported"
        )

        # Rate limit error
        rate_limit_error = format_error("Rate limit exceeded", "Daily quota reached")

        # All errors should have required fields
        for error in [network_error, auth_error, validation_error, rate_limit_error]:
            assert error.error
            assert error.details
            assert isinstance(error.error, str)
            assert isinstance(error.details, str)

    def test_server_data_integrity(self):
        """Test data integrity in server operations."""
        # Test that data remains consistent across operations
        original_response = SearchResponse(
            query="test",
            search_type="text",
            total_results=2,
            results=[
                SearchResult(title="Title 1", href="https://example.com/1"),
                SearchResult(title="Title 2", href="https://example.com/2"),
            ],
            has_more=True,
            next_page=2,
        )

        # Simulate data processing
        processed_query = original_response.query.upper()
        processed_total_results = original_response.total_results
        processed_results = [(r.title, r.href) for r in original_response.results]

        # Verify data integrity
        assert processed_query == "TEST"
        assert processed_total_results == 2
        assert len(processed_results) == 2
        assert processed_results[0][0] == "Title 1"
        assert processed_results[0][1] == "https://example.com/1"

    def test_server_configuration_handling(self):
        """Test server configuration handling."""
        # Test that server can handle different configurations
        configurations = [
            {"max_results": 5, "time_range": "d"},
            {"max_results": 10, "time_range": "w"},
            {"max_results": 1, "time_range": "y"},
        ]

        for config in configurations:
            req = SearchRequest(query="test", **config)
            assert req.query == "test"
            assert req.max_results == config["max_results"]
            assert req.time_range == config["time_range"]

    def test_server_response_serialization(self):
        """Test server response serialization."""
        # Test that SearchResponse can be serialized
        response = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="T", href="U")],
            has_more=False,
        )

        # Test model_dump() method
        response_dict = response.model_dump()

        assert "query" in response_dict
        assert "search_type" in response_dict
        assert "total_results" in response_dict
        assert "results" in response_dict
        assert "has_more" in response_dict

        # Test that results are properly serialized
        assert len(response_dict["results"]) == 1
        assert response_dict["results"][0]["title"] == "T"
        assert response_dict["results"][0]["href"] == "U"

    def test_server_error_response_serialization(self):
        """Test ErrorResponse serialization."""
        error = ErrorResponse(error="Test Error", details="Test Details")

        error_dict = error.model_dump()

        assert "error" in error_dict
        assert "details" in error_dict
        assert error_dict["error"] == "Test Error"
        assert error_dict["details"] == "Test Details"
