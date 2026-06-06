from unittest.mock import patch

from web_search_mcp.models import SearchResponse, SearchResult, ErrorResponse
from web_search_mcp.research import search_domain


def test_search_domain_success():
    """Test successful documentation search with explicit domain."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="site:docs.python.org test query",
            search_type="text",
            total_results=1,
            results=[SearchResult(title="Official Python Docs", href="https://docs.python.org")],
            has_more=False,
        )

        result = search_domain("test query", domain="docs.python.org")

        assert isinstance(result, SearchResponse)
        assert result.total_results == 1
        assert result.results[0].title == "Official Python Docs"
        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        # Verify the site: operator uses the domain exactly as provided
        assert "site:docs.python.org" in call_args.query


def test_search_domain_default():
    """Test documentation search uses default domain when none provided."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="site:docs.python.org test query",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )

        search_domain("test query")

        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert "site:docs.python.org" in call_args.query


def test_search_domain_dynamic_domain():
    """Test documentation search with a dynamic domain (e.g. github)."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="site:github.com test query",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )

        search_domain("test query", domain="github.com")

        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert "site:github.com" in call_args.query


def test_search_domain_failure():
    """Test handling of a failure in the underlying search function."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.side_effect = Exception("DDG is down")

        result = search_domain("test query", domain="react.dev")

        assert isinstance(result, ErrorResponse)
        assert "Search failed" in result.error
        assert "DDG is down" in result.details
