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
# Search (pure)
# ─────────────────────────────────────────────────────────────


def _build_search_params(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    count: int = 30,
) -> dict[str, str]:
    """Build the Algolia search request params from a query and date window."""
    core = _flatten_query(query)
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
    return params


def _normalize_search_hit(
    hit: dict[str, Any],
    query: str,
    rank: int,
) -> dict[str, Any] | None:
    """Normalize one Algolia hit into an HN item dict.

    Returns ``None`` when the title does not match the query so the caller can
    drop it. *rank* is the hit's position in the raw response (pre-filter).
    """
    object_id = hit.get("objectID", "")
    title = hit.get("title", "")
    if query and not _title_matches_query(title, query):
        return None
    points = hit.get("points") or 0
    num_comments = hit.get("num_comments") or 0
    created_at_i = hit.get("created_at_i")
    return {
        "id": object_id,
        "title": title,
        "url": hit.get("url") or "",
        "hn_url": f"https://news.ycombinator.com/item?id={object_id}",
        "author": hit.get("author", ""),
        "date": unix_to_date(created_at_i) if created_at_i else None,
        "engagement": {"points": points, "comments": num_comments},
        "relevance": compute_relevance(query, title, rank, points, engagement_weight=40.0),
        "why_relevant": f"HN: {title[:60]}",
    }


def _normalize_search_hits(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter, normalize, and rank a list of Algolia hits by relevance."""
    items: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits):
        item = _normalize_search_hit(hit, query, rank)
        if item is not None:
            items.append(item)
    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


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
    params = _build_search_params(query, from_date, to_date, count=count)
    logger.info("HN searching for '%s' (count=%d)", params["query"], count)

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

    return _normalize_search_hits(query, hits)


# ─────────────────────────────────────────────────────────────
# Comment enrichment
# ─────────────────────────────────────────────────────────────


def _extract_comments(children: list[dict[str, Any]], max_comments: int = 5) -> dict[str, Any]:
    """Reduce raw Algolia story children to top comments + one-line insights.

    Filters to real comments (non-empty text and author), ranks by points, and
    returns the top *max_comments* with HTML-stripped excerpts plus a distilled
    first-sentence insight for each.
    """
    real_comments = [c for c in children if c.get("text") and c.get("author")]
    real_comments.sort(key=lambda c: c.get("points") or 0, reverse=True)

    comments: list[dict[str, Any]] = []
    insights: list[str] = []
    for c in real_comments[:max_comments]:
        text = _strip_html(c.get("text", ""))
        excerpt = text[:300] + "..." if len(text) > 300 else text
        comments.append(
            {"author": c.get("author", ""), "text": excerpt, "points": c.get("points") or 0},
        )
        first_sentence = text.split(". ")[0].split("\n")[0][:200]
        if first_sentence:
            insights.append(first_sentence)

    return {"comments": comments, "comment_insights": insights}


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

    return _extract_comments(data.get("children", []), max_comments)


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
