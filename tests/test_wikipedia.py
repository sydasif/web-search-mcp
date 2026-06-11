"""Tests for Wikipedia search module."""

import unittest
from unittest.mock import patch, MagicMock

from web_search_mcp.wikipedia import (
    _search_wikipedia,
    _fetch_page_extract,
    wikipedia_search_tool,
)


_SEARCH_HITS = [
    {
        "title": "Python (programming language)",
        "pageid": 23862,
        "snippet": "Python is a high-level general-purpose programming language",
        "wordcount": 11797,
        "timestamp": "2024-01-01T00:00:00Z",
        "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
    },
    {
        "title": "History of Python",
        "pageid": 21356332,
        "snippet": "The history of Python",
        "wordcount": 4268,
        "timestamp": "2024-01-02T00:00:00Z",
        "url": "https://en.wikipedia.org/wiki/History_of_Python",
    },
]


class TestSearch(unittest.TestCase):
    """Tests for _search_wikipedia."""

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_returns_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "search": _SEARCH_HITS,
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _search_wikipedia("Python")
        assert len(results) == 2
        assert results[0]["title"] == "Python (programming language)"
        assert results[0]["pageid"] == 23862
        assert results[0]["wordcount"] == 11797
        assert "wikipedia.org" in results[0]["url"]

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"query": {"search": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _search_wikipedia("xyznonexistent12345")
        assert results == []

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _search_wikipedia("test")
        assert results == []

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_http_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        results = _search_wikipedia("test")
        assert results == []

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_missing_title(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "search": [
                    {"pageid": 123, "title": "Good", "wordcount": 100},
                    {"pageid": None, "wordcount": 50},
                    {"title": "", "pageid": 456, "wordcount": 75},
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _search_wikipedia("test")
        assert len(results) == 1
        assert results[0]["title"] == "Good"

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_search_caps_max_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"query": {"search": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        _search_wikipedia("test", max_results=999)
        call_url = mock_get.call_args[0][0]
        assert "srlimit=20" in call_url


class TestFetchPage(unittest.TestCase):
    """Tests for _fetch_page_extract."""

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_fetch_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "23862": {
                        "pageid": 23862,
                        "title": "Python (programming language)",
                        "extract": "Python is a programming language.\n\n== History ==\nPython was created...",
                    }
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text = _fetch_page_extract("Python (programming language)")
        assert text is not None
        assert "Python is a programming language" in text
        assert "== History ==" in text

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_fetch_missing_page(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "-1": {
                        "title": "Nonexistent page",
                        "missing": True,
                    }
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text = _fetch_page_extract("Nonexistent page")
        assert text is None

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_fetch_empty_extract(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "title": "Empty",
                        "extract": "",
                    }
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text = _fetch_page_extract("Empty")
        assert text is None

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_fetch_http_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        text = _fetch_page_extract("Any")
        assert text is None

    @patch("web_search_mcp.wikipedia.httpx.get")
    def test_fetch_no_extract_key(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "title": "No extract",
                    }
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text = _fetch_page_extract("No extract")
        assert text is None


class TestTool(unittest.TestCase):
    """Tests for wikipedia_search_tool (the MCP tool entry point)."""

    @patch("web_search_mcp.wikipedia._fetch_page_extract")
    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_full_output(self, mock_search, mock_fetch):
        mock_search.return_value = _SEARCH_HITS
        mock_fetch.return_value = "Python is a programming language.\n\n== History ==\n..."

        result = wikipedia_search_tool("Python")
        assert "Wikipedia: Python (programming language)" in result
        assert "**URL:** https://en.wikipedia.org/wiki/Python_(programming_language)" in result
        assert "**Word count:** 11,797" in result
        assert "Python is a programming language" in result
        assert "== History ==" in result
        assert "Related results" in result
        assert "History of Python" in result

    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_empty_query(self, mock_search):
        result = wikipedia_search_tool("   ")
        assert "Error" in result
        mock_search.assert_not_called()

    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_no_results(self, mock_search):
        mock_search.return_value = []
        result = wikipedia_search_tool("xyznonexistent12345")
        assert "No Wikipedia articles found" in result

    @patch("web_search_mcp.wikipedia._fetch_page_extract")
    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_fetch_fails_gracefully(self, mock_search, mock_fetch):
        mock_search.return_value = _SEARCH_HITS
        mock_fetch.return_value = None

        result = wikipedia_search_tool("Python")
        assert "Article text unavailable" in result
        assert "Python (programming language)" in result
        assert "Related results" in result

    @patch("web_search_mcp.wikipedia._fetch_page_extract")
    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_single_result_no_related(self, mock_search, mock_fetch):
        mock_search.return_value = [_SEARCH_HITS[0]]
        mock_fetch.return_value = "Some content"

        result = wikipedia_search_tool("Python")
        assert "Related results" not in result
        assert "Python (programming language)" in result

    @patch("web_search_mcp.wikipedia._fetch_page_extract")
    @patch("web_search_mcp.wikipedia._search_wikipedia")
    def test_tool_zero_wordcount(self, mock_search, mock_fetch):
        mock_search.return_value = [
            {
                "title": "Test",
                "pageid": 1,
                "wordcount": 0,
                "url": "https://en.wikipedia.org/wiki/Test",
                "timestamp": "",
            }
        ]
        mock_fetch.return_value = "Content"

        result = wikipedia_search_tool("Test")
        assert "Word count" not in result


if __name__ == "__main__":
    unittest.main()
