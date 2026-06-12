"""Tests for the arXiv search module."""

from unittest.mock import MagicMock, patch

import pytest

from web_search_mcp.arxiv import (
    search_arxiv,
    arxiv_search_tool,
    _format_arxiv_markdown,
)
from web_search_mcp.models import ErrorResponse


class MockPaper:
    """Minimal mock for arxiv.Result objects."""

    def __init__(self, title="Test Paper", authors=None, summary="Test abstract content",
                 pdf_url="https://arxiv.org/pdf/2401.00001",
                 published=None, updated=None,
                 primary_category="cs.AI", categories=None,
                 comment="", journal_ref="", doi=""):
        import datetime
        self.entry_id = "http://arxiv.org/abs/2401.00001v1"
        self.title = title
        self.authors = authors or [MagicMock(name="Author One"), MagicMock(name="Author Two")]
        self.summary = summary
        self.pdf_url = pdf_url
        self.published = published or datetime.datetime(2024, 1, 1)
        self.updated = updated or datetime.datetime(2024, 1, 15)
        self.primary_category = primary_category
        self.categories = categories or ["cs.AI", "cs.LG"]
        self.comment = comment
        self.journal_ref = journal_ref
        self.doi = doi


class TestSearchArxiv:
    """Tests for search_arxiv function."""

    @patch("web_search_mcp.arxiv.arxiv.Client")
    def test_successful_search(self, mock_client_cls):
        """Test successful paper search."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_paper = MockPaper()
        mock_client.results.return_value = [mock_paper]

        result = search_arxiv("machine learning", max_results=5)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Test Paper"
        assert result[0]["pdf_url"] == "https://arxiv.org/pdf/2401.00001"
        assert result[0]["primary_category"] == "cs.AI"

    @patch("web_search_mcp.arxiv.arxiv.Client")
    def test_empty_query_returns_error(self, mock_client_cls):
        """Test that empty query returns ErrorResponse."""
        result = search_arxiv("")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.arxiv.arxiv.Client")
    def test_whitespace_query_returns_error(self, mock_client_cls):
        """Test that whitespace-only query returns ErrorResponse."""
        result = search_arxiv("   ")
        assert isinstance(result, ErrorResponse)
        assert "empty" in result.error.lower()

    @patch("web_search_mcp.arxiv.arxiv.Client")
    def test_multiple_results(self, mock_client_cls):
        """Test multiple papers returned."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        papers = [MockPaper(title=f"Paper {i}") for i in range(3)]
        mock_client.results.return_value = papers

        result = search_arxiv("deep learning", max_results=3)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["title"] == "Paper 0"
        assert result[1]["title"] == "Paper 1"
        assert result[2]["title"] == "Paper 2"

    @patch("web_search_mcp.arxiv.arxiv.Client")
    def test_api_error_returns_error(self, mock_client_cls):
        """Test that API errors return ErrorResponse."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.results.side_effect = Exception("arXiv API unavailable")

        result = search_arxiv("test query")

        assert isinstance(result, ErrorResponse)
        assert "arXiv search failed" in result.error

    @patch("web_search_mcp.arxiv.arxiv.Client")
    @patch("web_search_mcp.arxiv.arxiv.Search")
    def test_max_results_capped(self, mock_search_cls, mock_client_cls):
        """Test that max_results is capped at 50."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        from web_search_mcp.arxiv import MAX_RESULTS_CAP

        search_arxiv("test", max_results=100)

        call_args = mock_search_cls.call_args[1]
        assert call_args["max_results"] == MAX_RESULTS_CAP


class TestFormatArxivMarkdown:
    """Tests for _format_arxiv_markdown."""

    def test_empty_papers(self):
        """Test formatting with empty list."""
        result = _format_arxiv_markdown([], "test query")
        assert "No arXiv results found for 'test query'." in result

    def test_single_paper(self):
        """Test formatting a single paper result."""
        papers = [{
            "title": "Deep Learning",
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "authors": ["Ian Goodfellow", "Yoshua Bengio"],
            "published": "2024-01-01",
            "categories": ["cs.AI", "cs.LG"],
            "summary": "A comprehensive overview of deep learning techniques.",
        }]
        result = _format_arxiv_markdown(papers, "deep learning")
        assert "# arXiv Results for 'deep learning'" in result
        assert "Found 1 papers." in result
        assert "Deep Learning" in result
        assert "Ian Goodfellow, Yoshua Bengio" in result
        assert "cs.AI, cs.LG" in result

    def test_multiple_papers(self):
        """Test formatting multiple papers with numbering."""
        papers = [
            {"title": "Paper A", "pdf_url": "#", "authors": ["Author A"], "summary": ""},
            {"title": "Paper B", "pdf_url": "#", "authors": ["Author B"], "summary": ""},
        ]
        result = _format_arxiv_markdown(papers, "test")
        assert "1." in result
        assert "2." in result

    def test_authors_truncated(self):
        """Test author truncation when > 3 authors."""
        papers = [{
            "title": "Many Authors",
            "pdf_url": "#",
            "authors": ["A", "B", "C", "D", "E"],
            "summary": "",
        }]
        result = _format_arxiv_markdown(papers, "test")
        assert "A, B, C et al." in result

    def test_no_date_shown(self):
        """Test paper with no published date."""
        papers = [{
            "title": "No Date Paper",
            "pdf_url": "#",
            "authors": [],
            "published": "",
            "categories": [],
            "summary": "",
        }]
        result = _format_arxiv_markdown(papers, "test")
        assert "No Date Paper" in result


class TestArxivSearchTool:
    """Tests for the arxiv_search_tool entry point."""

    @patch("web_search_mcp.arxiv.search_arxiv")
    def test_successful_tool_call(self, mock_search):
        """Test successful tool call returns formatted markdown."""
        mock_search.return_value = [{
            "title": "Paper",
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "authors": ["Author One"],
            "published": "2024-01-01",
            "categories": ["cs.AI"],
            "summary": "Abstract content.",
        }]

        result = arxiv_search_tool("test query")
        assert isinstance(result, str)
        assert "# arXiv Results for 'test query'" in result

    @patch("web_search_mcp.arxiv.search_arxiv")
    def test_no_results(self, mock_search):
        """Test tool with no results."""
        mock_search.return_value = []
        result = arxiv_search_tool("nonexistent topic")
        assert "No arXiv papers found" in result

    @patch("web_search_mcp.arxiv.search_arxiv")
    def test_error_response(self, mock_search):
        """Test tool passes through ErrorResponse."""
        mock_search.return_value = ErrorResponse(error="Test error", details="Test details")
        result = arxiv_search_tool("test")
        assert isinstance(result, ErrorResponse)
        assert result.error == "Test error"

    @patch("web_search_mcp.arxiv.search_arxiv")
    def test_max_results_passed(self, mock_search):
        """Test max_results parameter is forwarded."""
        mock_search.return_value = []
        arxiv_search_tool("test", max_results=20, sort_by="submitted_date")
        mock_search.assert_called_once_with(query="test", max_results=20, sort_by="submitted_date")


if __name__ == "__main__":
    pytest.main()
