import pytest
from pydantic import ValidationError
from web_search_mcp.models import SearchRequest


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
