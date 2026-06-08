"""Hacker News search via Algolia API (free, no auth required).

Uses hn.algolia.com/api/v1 for story discovery and comment enrichment.
No API key needed - just HTTP calls via httpx.
"""

import html as _html
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("web-search-mcp")

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items"

DEPTH_LIMITS = {"quick": 15, "default": 30, "deep": 60}
ENRICH_LIMITS = {"quick": 3, "default": 5, "deep": 10}
MAX_WORKERS = 5
TIMEOUT = 30

_HN_PREFIXES = re.compile(r"^(Tell HN|Show HN|Ask HN|Launch HN)\s*:\s*", re.IGNORECASE)
_WORD_BOUNDARY_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _date_to_unix(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix timestamp (start of day UTC)."""
    parts = date_str.split("-")
    dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
    return int(dt.timestamp())


def _unix_to_date(ts: int) -> str:
    """Convert Unix timestamp to YYYY-MM-DD."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


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
    for word in query_words:
        pattern = _WORD_BOUNDARY_RE_CACHE.get(word)
        if pattern is None:
            pattern = re.compile(rf"\b{re.escape(word)}\b")
            _WORD_BOUNDARY_RE_CACHE[word] = pattern
        if pattern.search(stripped):
            return True
    return False


def _compute_relevance(query: str, title: str, rank_index: int, points: int) -> float:
    """Blend text relevance with engagement signals."""
    rank_score = max(0.3, 1.0 - (rank_index * 0.02))
    engagement_boost = min(0.2, math.log1p(points) / 40)

    if query:
        q_tokens = set(query.lower().split())
        t_tokens = set(title.lower().split())
        overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
        content_score = min(1.0, overlap * 2)
        return round(min(1.0, 0.6 * rank_score + 0.4 * content_score + engagement_boost), 2)
    return round(min(1.0, rank_score * 0.7 + engagement_boost + 0.1), 2)


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


def search_hackernews(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    depth: str = "default",
) -> list[dict]:
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
        from_ts = _date_to_unix(from_date)
        to_ts = _date_to_unix(to_date) + 86400
        params["numericFilters"] = f"created_at_i>{from_ts},created_at_i<{to_ts},points>2"

    tokens = core.split()
    if len(tokens) > 1:
        params["optionalWords"] = " ".join(tokens[1:])

    url = f"{ALGOLIA_SEARCH_URL}?{urlencode(params)}"

    try:
        resp = httpx.get(url, timeout=TIMEOUT, headers={"User-Agent": "web-search-mcp/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("HN search failed: %s", e)
        return []

    hits = data.get("hits", [])
    logger.info("HN found %d stories", len(hits))

    items: list[dict] = []
    for i, hit in enumerate(hits):
        object_id = hit.get("objectID", "")
        points = hit.get("points") or 0
        num_comments = hit.get("num_comments") or 0
        created_at_i = hit.get("created_at_i")
        date_str = _unix_to_date(created_at_i) if created_at_i else None
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
                "relevance": _compute_relevance(query, title, i, points),
                "why_relevant": f"HN: {title[:60]}",
            }
        )

    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


# ─────────────────────────────────────────────────────────────
# Comment enrichment
# ─────────────────────────────────────────────────────────────


def _fetch_item_comments(object_id: str, max_comments: int = 5) -> dict:
    """Fetch top-level comments for a story from Algolia items endpoint."""
    url = f"{ALGOLIA_ITEM_URL}/{object_id}"
    try:
        resp = httpx.get(url, timeout=15, headers={"User-Agent": "web-search-mcp/1.0"})
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


def enrich_top_stories(items: list[dict], depth: str = "default") -> list[dict]:
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
