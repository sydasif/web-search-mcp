"""Extend existing LinkedIn intern tests: _build_results integration."""
from __future__ import annotations

from web_search_mcp._models import SearchResult
from web_search_mcp.social.linkedin import _build_results


def test_build_results_converts_items_to_search_result() -> None:
    items = [
        {
            "name": "Jane Doe",
            "url": "https://linkedin.com/in/jane",
            "headline": "ML Engineer",
            "snippet": "Building AI systems",
            "content_type": "people",
            "location": "SF",
            "about": "10 years in ML",
            "content_preview": "Post about transformers",
        }
    ]
    results = _build_results(items)
    assert len(results) == 1
    r = results[0]
    assert isinstance(r, SearchResult)
    assert r.title == "[People] Jane Doe"
    assert r.href == "https://linkedin.com/in/jane"
    body = r.body or ""
    assert "ML Engineer" in body
    assert "Building AI systems" in body
    assert "Location: SF" in body
    assert "About: 10 years in ML" in body
    assert "Preview: Post about transformers" in body


def test_build_results_minimal_item() -> None:
    items = [{"name": "Someone"}]
    results = _build_results(items)
    assert len(results) == 1
    assert results[0].title == "[Other] Someone"
    assert results[0].body is None  # no body parts available


def test_build_results_empty_list() -> None:
    assert _build_results([]) == []


def test_build_results_truncates_about_and_preview_to_200() -> None:
    long_text = "x" * 300
    items = [
        {
            "name": "N",
            "url": "u",
            "about": long_text,
            "content_preview": long_text,
        }
    ]
    results = _build_results(items)
    assert "About: " in (results[0].body or "")
    body = results[0].body or ""
    assert "Preview: " in body
    about_value = body.split("About: ")[1].split(" Preview: ")[0] if "Preview: " in body else body.split("About: ")[1]
    preview_value = body.split("Preview: ")[1] if "Preview: " in body else ""
    assert len(about_value) <= 200
    assert len(preview_value) <= 200
