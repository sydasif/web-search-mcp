from unittest.mock import patch, Mock
import datetime

from web_search_mcp.research import search_wiki, search_arxiv, search_docs


def test_search_wiki_success():
    """Test successful Wikipedia search."""
    with patch("web_search_mcp.research.wikipedia") as mock_wikipedia:
        mock_page = Mock()
        mock_page.title = "Test Page"
        mock_page.summary = "This is a test summary."
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"

        mock_wikipedia.search.return_value = ["Test Page", "Related Topic"]
        mock_wikipedia.page.return_value = mock_page

        result = search_wiki("test query")

        assert result["title"] == "Test Page"
        assert result["summary"] == "This is a test summary."
        assert "Related Topic" in result["related_topics"]
        mock_wikipedia.search.assert_called_once_with("test query")
        mock_wikipedia.page.assert_called_once_with("Test Page", auto_suggest=False)


def test_search_wiki_no_results():
    """Test Wikipedia search with no results found."""
    with patch("web_search_mcp.research.wikipedia") as mock_wikipedia:
        mock_wikipedia.search.return_value = []

        result = search_wiki("obscure query")

        assert "No Wikipedia pages found" in result["message"]
        assert result["results"] == []


def test_search_wiki_api_error():
    """Test error handling for Wikipedia API failure."""
    with patch("web_search_mcp.research.wikipedia") as mock_wikipedia:
        mock_wikipedia.search.side_effect = Exception("API error")

        result = search_wiki("test query")

        assert "error" in result
        assert "API error" in result["error"]


def test_search_arxiv_success():
    """Test successful ArXiv search."""
    with patch("web_search_mcp.research.arxiv.Search") as mock_arxiv_search:
        mock_result = Mock()
        mock_result.title = "Test Paper"
        mock_result.summary = "This is a test paper summary."

        # This is the key change: the mock author needs a .name attribute
        mock_author = Mock()
        mock_author.name = "Author 1"
        mock_result.authors = [mock_author]

        mock_result.pdf_url = "https://arxiv.org/pdf/1234.5678"
        mock_result.published = datetime.datetime(2023, 1, 1)

        mock_search_instance = mock_arxiv_search.return_value
        mock_search_instance.results.return_value = [mock_result]

        results = search_arxiv("test query", max_results=1)

        assert len(results) == 1
        assert results[0]["title"] == "Test Paper"
        assert "Author 1" in results[0]["authors"]
        assert results[0]["published"] == "2023-01-01"


def test_search_arxiv_no_results():
    """Test ArXiv search with no results."""
    with patch("web_search_mcp.research.arxiv.Search") as mock_arxiv_search:
        mock_search_instance = mock_arxiv_search.return_value
        mock_search_instance.results.return_value = []

        results = search_arxiv("unfindable research topic")

        assert len(results) == 0


def test_search_arxiv_api_error():
    """Test error handling for ArXiv API failure."""
    with patch("web_search_mcp.research.arxiv.Search") as mock_arxiv_search:
        mock_arxiv_search.side_effect = Exception("Connection timed out")

        results = search_arxiv("test query")

        assert len(results) == 1
        assert "error" in results[0]
        assert "Connection timed out" in results[0]["error"]


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
