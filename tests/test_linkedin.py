"""Regression tests for LinkedIn page parsing.

These guard the fix for a bug where Jina Reader markdown (which uses real
newlines) was parsed with ``\\n`` inside raw-string regexes, so patterns
matched the literal two-character sequence ``\n`` instead of a line break.
That caused name/headline/location/about extraction to capture an entire
document instead of the intended field.
"""

from __future__ import annotations

from web_search_mcp.social.linkedin import client

JINA_PROFILE = """# Jane Doe

Headline: Staff ML Engineer at Acme

Location: San Francisco, CA

About: Jane builds recommendation systems and has led the infra team since 2021.

Summary: Former researcher focused on NLP.
"""


def test_parse_linkedin_page_extracts_name_only() -> None:
    result = client._parse_linkedin_page("Title: Jane Doe", "https://www.linkedin.com/in/janedoe")
    assert result.get("name") == "Jane Doe"


def test_parse_linkedin_page_extracts_all_fields() -> None:
    result = client._parse_linkedin_page(JINA_PROFILE, "https://www.linkedin.com/in/janedoe")

    # Name must not swallow the rest of the document.
    assert result.get("name") == "Jane Doe"
    assert "\n" not in result.get("name", "")
    # Headline/location are real single-line fields.
    assert result.get("headline") == "Staff ML Engineer at Acme"
    assert result.get("location") == "San Francisco, CA"
    # About grabs the first paragraph only (stops at the blank line).
    assert result.get("about") == (
        "Jane builds recommendation systems and has led the infra team since 2021."
    )
    assert "Former researcher" not in result.get("about", "")


def test_parse_linkedin_page_empty_returns_empty_dict() -> None:
    assert client._parse_linkedin_page("", "https://www.linkedin.com/in/janedoe") == {}


def test_parse_linkedin_page_posts_preview_splits_on_real_newlines() -> None:
    url = "https://www.linkedin.com/posts/janedoe_123"
    content = (
        "Title: A post\n\nWe launched a new model today.\nIt is fast and small."
        "\n\nRead more at our blog."
    )
    result = client._parse_linkedin_page(content, url)
    preview = result.get("content_preview", "")
    # Newlines must split into discrete lines, not one blob with literal \n.
    assert "\n" in content  # sanity: source uses real newlines
    assert "launched a new model today." in preview
    assert "It is fast and small." in preview
