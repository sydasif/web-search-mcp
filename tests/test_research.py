from unittest.mock import patch

from web_search_mcp.research import search_docs


def test_search_docs_success():
    """Test successful documentation search."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = {
            "results": [{"title": "Official Python Docs"}],
            "total_results": 1,
        }

        result = search_docs("test query", tech_stack="python")

        assert result["total_results"] == 1
        assert "Official Python Docs" in result["results"][0]["title"]
        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert "site:docs.python.org" in call_args.query


def test_search_docs_unsupported_stack():
    """Test that an unsupported tech_stack defaults to Python."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = {}

        search_docs("test query", tech_stack="cobol")

        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert "site:docs.python.org" in call_args.query


def test_search_docs_failure():
    """Test handling of a failure in the underlying search function."""
    with patch("web_search_mcp.research.ddg_search") as mock_ddg_search:
        mock_ddg_search.side_effect = Exception("DDG is down")

        result = search_docs("test query", tech_stack="react")

        assert "error" in result
        assert "Search failed" in result["error"]
        assert "DDG is down" in result["details"]
