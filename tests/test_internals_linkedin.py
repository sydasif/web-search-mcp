"""Offline unit tests for LinkedIn search client internals."""

from __future__ import annotations

from web_search_mcp.social.linkedin import client


def test_build_ddg_query_site_scoping() -> None:
    assert client._build_ddg_query("data engineer", "all") == "site:linkedin.com data engineer"
    assert client._build_ddg_query("ceo", "people") == "site:linkedin.com/in/ ceo"
    assert client._build_ddg_query("openai", "companies") == "site:linkedin.com/company/ openai"
    assert client._build_ddg_query("ml", "posts") == "site:linkedin.com/posts/ ml"
    assert client._build_ddg_query("dev", "unknown") == "site:linkedin.com dev"


def test_categorize_url_detects_types() -> None:
    assert client.categorize_url("https://www.linkedin.com/in/jane-doe") == "people"
    assert client.categorize_url("https://www.linkedin.com/company/acme") == "companies"
    assert client.categorize_url("https://www.linkedin.com/posts/x") == "posts"
    assert client.categorize_url("https://www.linkedin.com/pulse/article") == "articles"
    assert client.categorize_url("https://www.linkedin.com/jobs/123") == "jobs"
    assert client.categorize_url("https://example.com/page") == "other"


def test_parse_search_result_structures_item() -> None:
    item = client._parse_search_result(
        title="Jane Doe - Staff Engineer at Acme",
        url="https://www.linkedin.com/in/jane-doe",
        body="python kubernetes distributed systems",
        query="python",
        index=0,
    )
    assert item["name"] == "Jane Doe"
    assert item["headline"] == "Staff Engineer at Acme"
    assert item["content_type"] == "people"
    assert item["url"] == "https://www.linkedin.com/in/jane-doe"
    assert 0.0 <= item["relevance"] <= 1.0


def test_parse_search_result_strips_linkedin_suffix() -> None:
    item = client._parse_search_result(
        title="Acme | LinkedIn",
        url="https://www.linkedin.com/company/acme",
        body="",
        query="acme",
        index=2,
    )
    assert item["name"] == "Acme"
    assert item["id"] == "LI3"


def test_parse_search_result_categorizes_by_path_pattern() -> None:
    # categorize_url matches the "/in/" path pattern regardless of host
    item = client._parse_search_result(
        title="Spam - LinkedIn",
        url="https://notlinkedin.com/in/x",
        body="",
        query="x",
        index=0,
    )
    assert item["content_type"] == "people"


def test_parse_linkedin_page_extracts_fields() -> None:
    content = (
        "# Jane Doe\n"
        "Headline: Staff Engineer\n"
        "Location: San Francisco, CA\n"
        "About: Builder of reliability tooling.\n"
        "\nMore text that is not a field.\n"
    )
    meta = client._parse_linkedin_page(content, "https://www.linkedin.com/in/jane-doe")
    assert meta["name"] == "Jane Doe"
    assert meta["headline"] == "Staff Engineer"
    assert meta["location"] == "San Francisco, CA"
    assert "reliability" in (meta.get("about") or "")
    assert meta["content_type"] == "people"


def test_parse_linkedin_page_empty_on_blank() -> None:
    assert client._parse_linkedin_page("", "https://www.linkedin.com/in/x") == {}


def test_parse_linkedin_page_preview_for_posts() -> None:
    content = "Some longer post body text that describes the update in detail."
    meta = client._parse_linkedin_page(content, "https://www.linkedin.com/posts/x")
    assert meta["content_type"] == "posts"
    assert "content_preview" in meta


def test_filter_by_type_returns_all_when_all() -> None:
    results = [
        {"url": "https://www.linkedin.com/in/a"},
        {"url": "https://www.linkedin.com/company/b"},
    ]
    assert client.filter_by_type(results, "all") == results


def test_filter_by_type_scopes_to_pattern() -> None:
    results = [
        {"url": "https://www.linkedin.com/in/a"},
        {"url": "https://www.linkedin.com/company/b"},
    ]
    filtered = client.filter_by_type(results, "companies")
    assert len(filtered) == 1
    assert filtered[0]["url"].endswith("/company/b")


def test_depth_limits_have_three_tiers() -> None:
    assert set(client.DEPTH_LIMITS.keys()) == {"quick", "default", "deep"}
    assert (
        client.DEPTH_LIMITS["deep"] > client.DEPTH_LIMITS["default"] > client.DEPTH_LIMITS["quick"]
    )
