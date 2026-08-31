"""Hacker News search via Algolia API (free, no auth required).

Uses hn.algolia.com/api/v1 for story discovery and comment enrichment.
No API key needed - just HTTP calls via httpx.
"""

from __future__ import annotations

import html as _html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cache
from typing import Any
from urllib.parse import urlencode

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._config import ENRICH_LIMITS as _ALL_ENRICH_LIMITS
from .._http import get_json_client
from .._models.types import Depth
from .._utils import compute_relevance, date_to_unix, format_results_markdown, unix_to_date

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items"

DEPTH_LIMITS = _ALL_DEPTH_LIMITS["hackernews"]
ENRICH_LIMITS = _ALL_ENRICH_LIMITS["hackernews"]
MAX_WORKERS = 5
TIMEOUT = 30

_HN_PREFIXES = re.compile(r"^(Tell HN|Show HN|Ask HN|Launch HN)\s*:\s*", re.IGNORECASE)





@cache
def _make_word_boundary_re(word: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(word)}\b")


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = _html.unescape(text)
    text = re.sub(r"<p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _flatten_query(query: str) -> str:
    """Normalise query for Algolia: hyphens and commas to spaces."""
    return " ".join(query.replace(",", " ").replace("-", " ").split())


def _title_matches_query(title: str, query: str) -> bool:
    """Check if any query token appears as a whole word in the title."""
    if not query:
        return True
    stripped = _HN_PREFIXES.sub("", title).strip().lower()
    query_words = [w for w in _flatten_query(query.lower()).split() if w]
    if not query_words:
        return True
    return any(_make_word_boundary_re(w).search(stripped) for w in query_words)


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


def search_hackernews(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    depth: Depth = "default",
) -> list[dict[str, Any]]:
    """Search Hacker News via Algolia API.

    Args:
        query: Search query
        from_date: Optional start date (YYYY-MM-DD)
        to_date: Optional end date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of normalized item dicts ready for pipeline use.

    """
    count = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"])
    core = _flatten_query(query)
    logger.info("HN searching for '%s' (count=%d)", core, count)

    params: dict[str, str] = {
        "query": core,
        "tags": "story",
        "hitsPerPage": str(count),
    }
    if from_date and to_date:
        from_ts = date_to_unix(from_date)
        to_ts = date_to_unix(to_date) + 86400
        params["numericFilters"] = f"created_at_i>{from_ts},created_at_i<{to_ts},points>2"

    tokens = core.split()
    if len(tokens) > 1:
        params["optionalWords"] = " ".join(tokens[1:])

    url = f"{ALGOLIA_SEARCH_URL}?{urlencode(params)}"

    try:
        with get_json_client(timeout=TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("HN search failed")
        return []

    hits = data.get("hits", [])
    logger.info("HN found %d stories", len(hits))

    items: list[dict] = []
    for i, hit in enumerate(hits):
        object_id = hit.get("objectID", "")
        points = hit.get("points") or 0
        num_comments = hit.get("num_comments") or 0
        created_at_i = hit.get("created_at_i")
        date_str = unix_to_date(created_at_i) if created_at_i else None
        article_url = hit.get("url") or ""
        hn_url = f"https://news.ycombinator.com/item?id={object_id}"
        title = hit.get("title", "")

        if query and not _title_matches_query(title, query):
            continue

        items.append(
            {
                "id": object_id,
                "title": title,
                "url": article_url,
                "hn_url": hn_url,
                "author": hit.get("author", ""),
                "date": date_str,
                "engagement": {"points": points, "comments": num_comments},
                "relevance": compute_relevance(query, title, i, points, engagement_weight=40.0),
                "why_relevant": f"HN: {title[:60]}",
            },
        )

    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


# ─────────────────────────────────────────────────────────────
# Comment enrichment
# ─────────────────────────────────────────────────────────────


def _fetch_item_comments(object_id: str, max_comments: int = 5) -> dict[str, Any]:
    """Fetch top-level comments for a story from Algolia items endpoint."""
    url = f"{ALGOLIA_ITEM_URL}/{object_id}"
    try:
        with get_json_client(timeout=TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("HN comment fetch failed for %s: %s", object_id, e)
        return {"comments": [], "comment_insights": []}

    children = data.get("children", [])
    real_comments = [c for c in children if c.get("text") and c.get("author")]
    real_comments.sort(key=lambda c: c.get("points") or 0, reverse=True)

    comments = []
    insights: list[str] = []
    for c in real_comments[:max_comments]:
        text = _strip_html(c.get("text", ""))
        excerpt = text[:300] + "..." if len(text) > 300 else text
        points = c.get("points") or 0
        author = c.get("author", "")
        comments.append({"author": author, "text": excerpt, "points": points})
        first_sentence = text.split(". ")[0].split("\n")[0][:200]
        if first_sentence:
            insights.append(first_sentence)

    return {"comments": comments, "comment_insights": insights}


def enrich_top_stories(
    items: list[dict[str, Any]], depth: Depth = "default"
) -> list[dict[str, Any]]:
    """Fetch comments for top N stories by points.

    Args:
        items: Parsed HN items
        depth: Research depth (controls enrichment count)

    Returns:
        Items with top_comments and comment_insights added.

    """
    if not items:
        return items

    limit = ENRICH_LIMITS.get(depth, ENRICH_LIMITS["default"])
    by_points = sorted(
        range(len(items)),
        key=lambda i: items[i].get("engagement", {}).get("points", 0),
        reverse=True,
    )
    to_enrich = by_points[:limit]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_item_comments, items[idx]["id"]): idx for idx in to_enrich
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result(timeout=15)
                items[idx]["top_comments"] = result["comments"]
                items[idx]["comment_insights"] = result["comment_insights"]
            except Exception as e:
                logger.warning("HN comment enrichment failed for %s: %s", items[idx].get("id"), e)

    return items


def format_hackernews_markdown(items: list[dict[str, Any]], query: str) -> str:
    """Format HN results as markdown."""

    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        points = item.get("engagement", {}).get("points", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        hn_url = item.get("hn_url", item.get("url", "#"))
        lines = [
            f"{i}. **[{item.get('title', 'Untitled')}]({hn_url})**",
            f"   {points} points, {comments} comments | {item.get('date', '')}",
        ]
        if item.get("top_comments"):
            lines.append("   Top comments:")
            for c in item["top_comments"][:2]:
                lines.append(f"   > {c.get('text', '')[:200]}...")
        return lines

    return format_results_markdown(items, query, "Hacker News", "stories", _item_lines)
