"""LinkedIn search client — DuckDuckGo search + Jina Reader enrichment.

1. Search DDG with site:linkedin.com query.
2. Enrich results via Jina Reader (r.jina.ai) for clean markdown content.
3. Parse LinkedIn page types: people, companies, posts, jobs, articles.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx
from ddgs import DDGS

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._config import ENRICH_LIMITS as _ALL_ENRICH_LIMITS
from ..._models.types import Depth
from ..._utils import compute_relevance, format_results_markdown, token_overlap_relevance

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

# LinkedIn URL path patterns for content type detection
LINKEDIN_TYPE_PATTERNS: dict[str, str] = {
    "people": "/in/",
    "companies": "/company/",
    "posts": "/posts/",
    "articles": "/pulse/",
    "jobs": "/jobs/",
}

# Site search query templates for DDG
_SITE_QUERY_TEMPLATES: dict[str, str] = {
    "all": "site:linkedin.com {query}",
    "people": "site:linkedin.com/in/ {query}",
    "companies": "site:linkedin.com/company/ {query}",
    "posts": "site:linkedin.com/posts/ {query}",
    "articles": "site:linkedin.com/pulse/ {query}",
    "jobs": "site:linkedin.com/jobs/ {query}",
}

# Jina Reader API endpoint (agent-reach fallback approach)
_JINA_READER_URL = "https://r.jina.ai/"

# Regex patterns for parsing Jina Reader markdown output.
# NOTE: Jina returns real newlines, so these match \n (not the literal
# two-character sequence \\n that a raw string would otherwise produce).
_NAME_RE = re.compile(r"(?:^Title:\s*|^#\s+)(.+?)(?:\s*\||\n|$)")
_HEADLINE_RE = re.compile(r"(?:Headline|Title):\s*(.+?)(?:\n|$)", re.IGNORECASE)
_LOCATION_RE = re.compile(r"(?:Location):\s*(.+?)(?:\n|$)", re.IGNORECASE)
_ABOUT_RE = re.compile(r"(?:About|Summary):\s*(.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL)

# Type emojis
_TYPE_EMOJI: dict[str, str] = {
    "people": "\U0001f464",
    "companies": "\U0001f3e2",
    "posts": "\U0001f4dd",
    "articles": "\U0001f4c4",
    "jobs": "\U0001f4bc",
    "other": "\U0001f517",
}

DEPTH_LIMITS = _ALL_DEPTH_LIMITS["linkedin"]
ENRICH_LIMITS = _ALL_ENRICH_LIMITS["linkedin"]
MAX_WORKERS = 4
TIMEOUT = 30


def _build_ddg_query(query: str, content_type: str) -> str:
    """Build a DDG search query with site: filter."""
    template = _SITE_QUERY_TEMPLATES.get(content_type, _SITE_QUERY_TEMPLATES["all"])
    return template.format(query=query)


def _search_via_ddg(
    query: str,
    content_type: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search LinkedIn via DuckDuckGo with site:linkedin.com filter."""
    ddg_query = _build_ddg_query(query, content_type)
    logger.info("LinkedIn DDG search: %s (max=%d)", ddg_query, max_results)

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(ddg_query, max_results=max_results))
    except Exception as e:
        logger.warning("DDG search failed for LinkedIn: %s", e)
        return []

    parsed: list[dict[str, Any]] = []
    for i, r in enumerate(raw_results):
        url = r.get("href") or r.get("url") or ""
        if "linkedin.com" not in url:
            continue
        item = _parse_search_result(
            title=r.get("title", ""),
            url=url,
            body=r.get("body", ""),
            query=query,
            index=i,
        )
        parsed.append(item)

    return parsed


def _parse_search_result(
    title: str,
    url: str,
    body: str,
    query: str,
    index: int,
) -> dict[str, Any]:
    """Parse a DDG search result snippet into a structured LinkedIn item."""
    clean_title = title.replace(" | LinkedIn", "").strip()
    parts = clean_title.split(" - ")
    name = parts[0].strip() if parts else clean_title
    headline = " - ".join(parts[1:]).strip() if len(parts) > 1 else ""

    content_type = categorize_url(url)
    relevance = compute_relevance(query, title, index, 0)
    token_rel = token_overlap_relevance(query, f"{name} {headline} {body}")

    return {
        "id": f"LI{index + 1}",
        "name": name,
        "headline": headline,
        "snippet": body[:500] if body else "",
        "url": url,
        "content_type": content_type,
        "relevance": max(relevance, token_rel),
        "why_relevant": f"LinkedIn {content_type}: {name[:60]}",
        "engagement": {},
    }


def categorize_url(url: str) -> str:
    """Categorize a LinkedIn URL by content type."""
    for content_type, pattern in LINKEDIN_TYPE_PATTERNS.items():
        if pattern in url:
            return content_type
    return "other"


def filter_by_type(
    results: list[dict[str, Any]],
    content_type: str,
) -> list[dict[str, Any]]:
    """Filter search results by LinkedIn content type. 'all' returns everything."""
    if content_type == "all":
        return results

    pattern = LINKEDIN_TYPE_PATTERNS.get(content_type, "")
    if not pattern:
        return results

    return [r for r in results if pattern in (r.get("url") or r.get("href") or "")]


def _fetch_page_via_jina(url: str, timeout: int = TIMEOUT) -> str | None:
    """Fetch a LinkedIn page using Jina Reader API (r.jina.ai).

    Mirrors the agent-reach fallback strategy: use Jina to bypass bot protection
    and return clean markdown.
    """
    jina_url = f"{_JINA_READER_URL}{url}"

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                jina_url,
                headers={"Accept": "text/markdown"},
            )
            response.raise_for_status()

            content = response.text
            if content and len(content) > 100:
                return content
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.debug("Jina fetch failed for %s: %s", url, e)

    return None


def _parse_linkedin_page(content: str, url: str) -> dict[str, Any]:
    """Extract metadata from LinkedIn page content fetched via Jina Reader."""
    if not content:
        return {}

    result: dict[str, Any] = {}
    content_type = categorize_url(url)
    result["content_type"] = content_type

    name_match = _NAME_RE.search(content)
    if name_match:
        result["name"] = name_match.group(1).strip()

    headline_match = _HEADLINE_RE.search(content)
    if headline_match:
        result["headline"] = headline_match.group(1).strip()

    location_match = _LOCATION_RE.search(content)
    if location_match:
        result["location"] = location_match.group(1).strip()

    about_match = _ABOUT_RE.search(content)
    if about_match:
        result["about"] = about_match.group(1).strip()[:1000]

    if content_type in ("posts", "articles"):
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip() and not line.startswith("#") and not line.startswith("Title:")
        ]
        if lines:
            result["content_preview"] = " ".join(lines[:10])[:1000]

    return result


def _enrich_one(item: dict[str, Any]) -> dict[str, Any]:
    """Enrich a single LinkedIn result via Jina Reader."""
    url = item.get("url", "")
    if not url:
        return item

    try:
        content = _fetch_page_via_jina(url)
        if content:
            metadata = _parse_linkedin_page(content, url)
            if metadata:
                for key, value in metadata.items():
                    if value and not item.get(key):
                        item[key] = value
    except Exception as e:
        logger.debug("LinkedIn enrichment failed for %s: %s", url, e)

    return item


def enrich_linkedin_results(
    results: list[dict[str, Any]],
    depth: Depth = "default",
) -> list[dict[str, Any]]:
    """Enrich top LinkedIn results by fetching page content via Jina AI."""
    if not results:
        return results

    limit = ENRICH_LIMITS.get(depth, ENRICH_LIMITS["default"])
    to_enrich = results[:limit]

    logger.info("LinkedIn enriching top %d results via Jina Reader", len(to_enrich))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_enrich_one, item): i for i, item in enumerate(to_enrich)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                to_enrich[idx] = future.result(timeout=20)
            except Exception as e:
                logger.debug("LinkedIn enrichment future failed for index %d: %s", idx, e)

    return results


def search_linkedin(
    query: str,
    content_type: str = "all",
    max_results: int = 25,
    depth: Depth = "default",
) -> list[dict[str, Any]]:
    """Search LinkedIn via DDG and enrich results.

    Args:
        query: Search query string
        content_type: Content type filter
            ('all', 'people', 'companies', 'posts', 'articles', 'jobs')
        max_results: Maximum results to return (capped by depth limits)
        depth: Search depth ('quick', 'default', 'deep') - controls
            result limits and enrichment

    Returns:
        List of structured LinkedIn result dicts
    """
    if not query or not query.strip():
        return []

    # Cap results by depth limits
    max_results = min(max_results, DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"]))

    # Search via DDG
    results = _search_via_ddg(query, content_type, max_results)

    # Filter by content type if specified
    if content_type != "all":
        results = filter_by_type(results, content_type)

    # Enrich top results
    results = enrich_linkedin_results(results, depth)

    # Sort by relevance
    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    return results[:max_results]


def format_linkedin_markdown(items: list[dict[str, Any]], query: str) -> str:
    """Format LinkedIn results as markdown."""

    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        name = item.get("name", "Unknown")
        url = item.get("url", "#")
        headline = item.get("headline", "")
        snippet = item.get("snippet", "")
        content_type = item.get("content_type", "other")

        emoji = _TYPE_EMOJI.get(content_type, _TYPE_EMOJI["other"])

        lines: list[str] = [
            f"{i}. {emoji} **[{name}]({url})**",
        ]
        if headline:
            lines.append(f"   {headline}")
        if snippet:
            lines.append(f"   {snippet[:200]}{'...' if len(snippet) > 200 else ''}")

        if item.get("location"):
            lines.append(f"   \U0001f4cd {item['location']}")
        if item.get("about"):
            lines.append(f"   {item['about'][:200]}...")
        if item.get("content_preview"):
            lines.append(f"   {item['content_preview'][:200]}...")

        return lines

    return format_results_markdown(items, query, "LinkedIn Search", "results", _item_lines)
