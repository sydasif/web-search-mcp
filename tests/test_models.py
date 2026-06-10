import pytest
from pydantic import ValidationError
from web_search_mcp.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    PageResponse,
    ErrorResponse,
)


def test_search_request_valid_defaults():
    """Test SearchRequest with only required fields."""
    req = SearchRequest(query="python programming")
    assert req.query == "python programming"
    assert req.search_type == "text"
    assert req.max_results == 5
    assert req.page == 1
    assert req.safesearch == "moderate"
    assert req.backend == "auto"
    assert req.response_format == "markdown"


def test_search_request_valid_custom():
    """Test SearchRequest with custom valid fields."""
    req = SearchRequest(
        query="Claude AI",
        search_type="news",
        max_results=10,
        time_range="d",
        region="us-en",
        safesearch="off",
        page=2,
        backend="api",
        response_format="json",
    )
    assert req.query == "Claude AI"
    assert req.search_type == "news"
    assert req.max_results == 10
    assert req.time_range == "d"
    assert req.region == "us-en"
    assert req.safesearch == "off"
    assert req.page == 2
    assert req.backend == "api"
    assert req.response_format == "json"


def test_search_request_invalid_max_results():
    """Test that max_results < 1 raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", max_results=0)
    assert "Input should be greater than or equal to 1" in str(excinfo.value)


def test_search_request_invalid_page():
    """Test that page < 1 raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", page=0)
    assert "Input should be greater than or equal to 1" in str(excinfo.value)


def test_search_request_invalid_search_type():
    """Test that an unsupported search_type raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", search_type="images")
    assert "Input should be 'text' or 'news'" in str(excinfo.value)


def test_search_request_invalid_safesearch():
    """Test that an unsupported safesearch value raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", safesearch="none")
    assert "Input should be 'moderate', 'off' or 'on'" in str(excinfo.value)


def test_search_request_invalid_backend():
    """Test that an unsupported backend raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", backend="google")
    assert "Input should be 'auto', 'legacy' or 'api'" in str(excinfo.value)


def test_search_request_invalid_response_format():
    """Test that an unsupported response_format raises ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        SearchRequest(query="test", response_format="xml")
    assert "Input should be 'json' or 'markdown'" in str(excinfo.value)


def test_search_request_edge_cases():
    """Test edge cases for SearchRequest."""
    # Test very long query
    long_query = "x" * 1000
    req = SearchRequest(query=long_query, max_results=1)
    assert req.query == long_query

    # Test max_results boundary values
    req = SearchRequest(query="test", max_results=1)
    assert req.max_results == 1

    # Test page boundary values
    req = SearchRequest(query="test", page=1)
    assert req.page == 1

    # Test time_range values
    req = SearchRequest(query="test", time_range="y")
    assert req.time_range == "y"

    # Test region values
    req = SearchRequest(query="test", region="uk-en")
    assert req.region == "uk-en"


def test_search_request_special_characters():
    """Test SearchRequest with special characters."""
    special_query = "Python & JavaScript: What's the best? 🚀"
    req = SearchRequest(query=special_query, max_results=1)
    assert req.query == special_query

    # Test URL with special characters
    req = SearchRequest(query="site:example.com/path?query=value#fragment", max_results=1)
    assert req.query == "site:example.com/path?query=value#fragment"


def test_search_result_creation():
    """Test SearchResult model creation."""
    # Test with all fields
    result = SearchResult(
        title="Test Title",
        href="https://example.com",
        url="https://example.com",
        body="Test body content",
    )
    assert result.title == "Test Title"
    assert result.href == "https://example.com"
    assert result.url == "https://example.com"
    assert result.body == "Test body content"

    # Test with partial fields
    result = SearchResult(title="Title Only", href="https://example.com")
    assert result.title == "Title Only"
    assert result.href == "https://example.com"
    assert result.url is None
    assert result.body is None

    # Test with empty strings
    result = SearchResult(title="", href="", body="")
    assert result.title == ""
    assert result.href == ""
    assert result.body == ""


def test_search_result_url_resolution():
    """Test URL resolution priority in SearchResult."""
    # href takes priority over url
    result = SearchResult(href="https://href.com", url="https://url.com")
    assert result.href == "https://href.com"
    assert result.url == "https://url.com"

    # url used when href is None
    result = SearchResult(url="https://url.com")
    assert result.url == "https://url.com"
    assert result.href is None

    # No URL results in None
    result = SearchResult()
    assert result.href is None
    assert result.url is None


def test_search_response_structure():
    """Test SearchResponse structure and validation."""
    # Test with minimal required fields
    response = SearchResponse(
        query="test", search_type="text", total_results=0, results=[], has_more=False
    )
    assert response.query == "test"
    assert response.search_type == "text"
    assert response.total_results == 0
    assert response.results == []
    assert response.has_more is False
    assert response.next_page is None
    assert response.error is None
    assert response.details is None

    # Test with all fields
    response = SearchResponse(
        query="test",
        search_type="news",
        total_results=10,
        results=[
            SearchResult(title="Result 1", href="https://example.com/1"),
            SearchResult(title="Result 2", href="https://example.com/2"),
        ],
        has_more=True,
        next_page=2,
        error="API rate limited",
        details="Exceeded daily limit",
    )
    assert response.query == "test"
    assert response.search_type == "news"
    assert response.total_results == 10
    assert len(response.results) == 2
    assert response.has_more is True
    assert response.next_page == 2
    assert response.error == "API rate limited"
    assert response.details == "Exceeded daily limit"


def test_search_response_error_scenarios():
    """Test SearchResponse error handling scenarios."""
    # Test error response from SearchResponse (should not happen based on model design)
    # This would be ErrorResponse instead, but testing edge case

    # Test empty query scenario
    response = SearchResponse(
        query="",
        search_type="text",
        total_results=0,
        results=[],
        has_more=False,
        error="Empty query",
    )
    assert response.query == ""
    assert response.error == "Empty query"


def test_page_response_creation():
    """Test PageResponse model creation."""
    # Test with all fields
    response = PageResponse(
        url="https://example.com",
        length=1500,
        content="Extracted page content",
        metadata={
            "title": "Page Title",
            "author": "John Doe",
            "date": "2023-01-01",
            "description": "Page description",
        },
        warning="Content truncated",
    )
    assert response.url == "https://example.com"
    assert response.length == 1500
    assert response.content == "Extracted page content"
    if response.metadata:
        assert response.metadata["title"] == "Page Title"
    assert response.warning == "Content truncated"

    # Test with minimal fields
    response = PageResponse(url="https://example.com", length=100, content="Short content")
    assert response.url == "https://example.com"
    assert response.length == 100
    assert response.content == "Short content"
    assert response.metadata is None
    assert response.warning is None

    # Test with empty content
    response = PageResponse(url="https://example.com", length=0, content="")
    assert response.length == 0
    assert response.content == ""


def test_page_response_truncation():
    """Test PageResponse content truncation."""
    long_content = "x" * 20000
    response = PageResponse(
        url="https://example.com", length=len(long_content), content=long_content
    )
    # The max_length should be applied during fetch operations
    # This test ensures the model accepts the content length
    assert response.length == 20000
    assert len(response.content) == 20000


def test_error_response_creation():
    """Test ErrorResponse model creation."""
    # Test with both fields
    error = ErrorResponse(error="Search failed", details="Invalid API key provided")
    assert error.error == "Search failed"
    assert error.details == "Invalid API key provided"

    # Test error message formatting
    error = ErrorResponse(error="Connection timeout", details="Request took longer than 30 seconds")
    assert "timeout" in error.error.lower()
    assert "30 seconds" in error.details


def test_model_validation_scenarios():
    """Test various validation scenarios for all models."""
    # Test SearchResult with None values
    result = SearchResult()
    assert result.title is None
    assert result.href is None
    assert result.url is None
    assert result.body is None

    # Test SearchResponse with negative results
    response = SearchResponse(
        query="test",
        search_type="text",
        total_results=-1,  # This should be allowed by Pydantic (no validator)
        results=[],
        has_more=False,
    )
    assert response.total_results == -1  # Pydantic doesn't enforce >0 without validator

    # Test PageResponse with negative length
    response = PageResponse(url="https://example.com", length=-100, content="")
    assert response.length == -100


def test_model_serialization():
    """Test model serialization to dict."""
    result = SearchResult(title="Test", href="https://example.com")
    result_dict = result.model_dump()
    assert result_dict["title"] == "Test"
    assert result_dict["href"] == "https://example.com"
    assert "url" in result_dict
    assert "body" in result_dict

    response = SearchResponse(
        query="test", search_type="text", total_results=1, results=[result], has_more=False
    )
    response_dict = response.model_dump()
    assert response_dict["query"] == "test"
    assert response_dict["total_results"] == 1
    assert "results" in response_dict


def test_model_field_types():
    """Test that models maintain correct field types."""
    # SearchResult field types
    result = SearchResult(title="Test", href="https://example.com", body="Body")
    assert isinstance(result.title, str)
    assert isinstance(result.href, str)
    assert result.url is None  # url is optional and defaults to None
    assert isinstance(result.body, str)

    # SearchResponse field types
    response = SearchResponse(
        query="test", search_type="text", total_results=5, results=[], has_more=False
    )
    assert isinstance(response.query, str)
    assert isinstance(response.search_type, str)
    assert isinstance(response.total_results, int)
    assert isinstance(response.results, list)
    assert isinstance(response.has_more, bool)

    # PageResponse field types
    page_response = PageResponse(url="https://example.com", length=100, content="Content")
    assert isinstance(page_response.url, str)
    assert isinstance(page_response.length, int)
    assert isinstance(page_response.content, str)
    assert page_response.metadata is None  # metadata is optional and defaults to None
