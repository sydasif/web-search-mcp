from unittest.mock import patch
from web_search_mcp.models import SearchRequest, SearchResponse, SearchResult, ErrorResponse
from web_search_mcp.search import ddg_search, format_search_results_markdown


class TestDDGSearch:
    """Test suite for DDG search functionality with mocked DDGS API calls."""

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_basic_text(self, mock_ddgs_class):
        """Test basic text search functionality."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {
                "title": "Test Result",
                "href": "https://example.com",
                "body": "Test description",
            }
        ]

        req = SearchRequest(query="test query", max_results=1)
        result = ddg_search(req)

        assert result.query == "test query"
        assert result.search_type == "text"
        assert result.total_results == 1
        assert len(result.results) == 1
        mock_ddgs.text.assert_called_once_with(
            "test query",
            max_results=1,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_with_time_filter(self, mock_ddgs_class):
        """Test search with time range filter."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test query", time_range="d", max_results=2)
        result = ddg_search(req)

        assert result.search_type == "text"
        assert len(result.results) == 0
        mock_ddgs.text.assert_called_once_with(
            "test query",
            max_results=2,
            timelimit="d",
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_with_all_common_params(self, mock_ddgs_class):
        """Test search with all common parameters."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.news.return_value = []

        req = SearchRequest(
            query="test query",
            search_type="news",
            max_results=5,
            time_range="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )
        result = ddg_search(req)

        assert result.search_type == "news"
        mock_ddgs.news.assert_called_once_with(
            "test query",
            max_results=5,
            timelimit="w",
            region="us-en",
            safesearch="off",
            page=2,
            backend="api",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_error_handling(self, mock_ddgs_class):
        """Test error handling when DDG API fails."""
        mock_ddgs_class.return_value.__enter__.side_effect = Exception("Network error")

        req = SearchRequest(query="test query", max_results=1)
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "Network error" in result.error

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_default_type(self, mock_ddgs_class):
        """Test that default search type is 'text'."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test")
        result = ddg_search(req)

        assert result.search_type == "text"
        mock_ddgs.text.assert_called_once()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_none_params_not_passed(self, mock_ddgs_class):
        """Test that None parameters are not passed to DDG."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(
            query="test",
            max_results=5,
            time_range=None,
            region=None,
            page=1,
        )
        result = ddg_search(req)
        assert result.query == "test"
        assert result.search_type == "text"

        # Verify that only non-None parameters are passed
        call_kwargs = mock_ddgs.text.call_args[1]
        assert "max_results" in call_kwargs
        assert "timelimit" not in call_kwargs  # None parameter should be filtered
        assert "region" not in call_kwargs  # None parameter should be filtered
        # But defaults should still be present
        assert "safesearch" in call_kwargs

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_empty_query(self, mock_ddgs_class):
        """Test that an empty query returns an error."""
        req = SearchRequest(query="")
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "Query cannot be empty" in result.error
        mock_ddgs_class.return_value.__enter__.return_value.text.assert_not_called()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_invalid_search_type(self, mock_ddgs_class):
        """Test that an invalid search_type returns an error."""
        req = SearchRequest(query="test", search_type="text")
        req.search_type = "invalid_type"  # type: ignore
        result = ddg_search(req)

        assert isinstance(result, ErrorResponse)
        assert "Unsupported search type: invalid_type" in result.error
        mock_ddgs_class.return_value.__enter__.return_value.text.assert_not_called()

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_no_results(self, mock_ddgs_class):
        """Test that the search handles no results from the API."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="a very specific query with no results")
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 0
        assert len(result.results) == 0

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_max_results_zero(self, mock_ddgs_class):
        """Test that max_results=0 is handled correctly."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = []

        req = SearchRequest(query="test", max_results=1)  # Create with valid value
        req.max_results = 0  # Set to 0 to bypass validation
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 0
        assert len(result.results) == 0
        mock_ddgs.text.assert_called_once_with(
            "test",
            max_results=0,
            safesearch="moderate",
            page=1,
            backend="auto",
        )

    @patch("web_search_mcp.search.DDGS")
    def test_ddg_search_malformed_api_response(self, mock_ddgs_class):
        """Test robustness against malformed API responses."""
        mock_ddgs = mock_ddgs_class.return_value.__enter__.return_value
        mock_ddgs.text.return_value = [
            {"title": "Only title"},  # Missing href and body
            {"href": "https://example.com"},  # Missing title and body
        ]

        req = SearchRequest(query="test", max_results=2)
        result = ddg_search(req)

        assert isinstance(result, SearchResponse)
        assert result.total_results == 2
        assert len(result.results) == 2
        # Check that the available data is still parsed
        assert result.results[0].title == "Only title"
        assert result.results[0].href is None
        assert result.results[1].title is None
        assert result.results[1].href == "https://example.com"


class TestFormatSearchResultsMarkdown:
    """Test suite for search results markdown formatting."""

    def test_format_error_response(self):
        """Test formatting of ErrorResponse objects."""
        err = ErrorResponse(error="API failure", details="Timeout")
        result = format_search_results_markdown(err)
        assert result == "**Error:** API failure"

    def test_format_error_with_details(self):
        """Test formatting of ErrorResponse with details."""
        err = ErrorResponse(error="Custom error", details="extra info")
        result = format_search_results_markdown(err)
        assert result == "**Error:** Custom error"

    def test_format_empty_search(self):
        """Test formatting of empty search results."""
        res = SearchResponse(
            query="test",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )
        result = format_search_results_markdown(res)
        assert "# Search Results for 'test' (text)" in result
        assert "Found 0 results." in result
        assert "No results found." in result

    def test_format_result_types(self):
        """Test formatting with SearchResult models."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=2,
            results=[
                SearchResult(title="Title One", href="https://one.com", body="Body one"),
                SearchResult(title="Title Two", href="https://two.com", body="Body two"),
            ],
            has_more=False,
            next_page=None,
        )
        result = format_search_results_markdown(results)
        assert "**[Title One](https://one.com)**" in result
        assert "Body one" in result
        assert "**[Title Two](https://two.com)**" in result
        assert "Body two" in result

    def test_format_url_fallbacks(self):
        """Test URL fallback logic (href -> url -> #)."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=3,
            results=[
                SearchResult(title="T1", href="https://href.com"),
                SearchResult(title="T2", url="https://url.com"),
                SearchResult(title="T3"),  # Both missing
            ],
            has_more=False,
        )
        result = format_search_results_markdown(results)
        assert "[T1](https://href.com)" in result
        assert "[T2](https://url.com)" in result
        assert "[T3](#)" in result

    def test_format_body_omission(self):
        """Test that results with empty or None bodies omit the body line."""
        results = SearchResponse(
            query="test",
            search_type="text",
            total_results=3,
            results=[
                SearchResult(title="T1", href="https://1.com", body=""),
                SearchResult(title="T2", href="https://2.com", body=None),
                SearchResult(title="T3", href="https://3.com", body="Exists"),
            ],
            has_more=False,
        )
        result = format_search_results_markdown(results)
        lines = result.split("\n")
        body_lines = [line for line in lines if line.startswith("   ")]
        assert len(body_lines) == 1
        assert "Exists" in body_lines[0]

    def test_format_pagination(self):
        """Test the pagination footer."""
        # Pagination active
        res_active = SearchResponse(
            query="test",
            search_type="text",
            total_results=10,
            results=[SearchResult(title="T", href="U", body="B")],
            has_more=True,
            next_page=2,
        )
        assert "More results available. See page 2." in format_search_results_markdown(res_active)

        # Pagination inactive
        res_inactive = SearchResponse(
            query="test",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="T", href="U", body="B")],
            has_more=False,
            next_page=None,
        )
        assert "More results available" not in format_search_results_markdown(res_inactive)
