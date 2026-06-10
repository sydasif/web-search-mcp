"""Keyless Reddit parsing logic: RSS discovery and Shreddit enrichment.
Consolidates RSS/Atom feed parsing and Shreddit HTML parsing.
"""

import logging
import re
import xml.etree.ElementTree as ET
import html as _html
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from . import client
from ..utils import token_overlap_relevance

logger = logging.getLogger(__name__)

# ── RSS/Atom Constants ─────────────────────────────────────────────────────
ATOM = "{http://www.w3.org/2005/Atom}"
DEPTH_LIMITS = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}
LISTING_SORTS = {
    "quick": ["top"],
    "default": ["top", "hot"],
    "deep": ["top", "hot", "new"],
}
MAX_WORKERS = 4
FEED_TIMEOUT = 15

# ── Shreddit Constants ─────────────────────────────────────────────────────
ENRICH_LIMITS = {
    "quick": 3,
    "default": 5,
    "deep": 8,
}
MAX_COMMENTS = 10
SVC_TIMEOUT = 12
_COMMENT_START = re.compile(r"<shreddit-comment(?=[\s>])[^>]*>")
_TOTAL_COMMENTS = re.compile(r'total-comments="(\d+)"')
_PARA = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_NEXT_RTJSON = re.compile(r'id="t1_[A-Za-z0-9]+-(?:comment|post)-rtjson-content"')


# ── RSS/Atom Helpers ───────────────────────────────────────────────────────


def _iso_to_date(value: str | None) -> str | None:
    """Parse an ISO-8601 timestamp to YYYY-MM-DD."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return None


def _iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _subreddit_from(category: str, url: str) -> str:
    """Derive subreddit name from the entry category or, failing that, the URL."""
    if category:
        return category
    parts = url.split("/r/", 1)
    if len(parts) == 2:
        return parts[1].split("/", 1)[0]
    return ""


def _parse_feed(xml_text: str, query: str = "") -> list[dict[str, Any]]:
    """Parse an Atom feed string into normalized post dicts. Never raises."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.debug("feed parse error: %s", e)
        return []

    posts: list[dict[str, Any]] = []
    for entry in root.iter(f"{ATOM}entry"):
        link_el = entry.find(f"{ATOM}link")
        url = link_el.get("href", "").strip() if link_el is not None else ""
        if not url or "/comments/" not in url:
            continue

        title_el = entry.find(f"{ATOM}title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        author = ""
        author_el = entry.find(f"{ATOM}author/{ATOM}name")
        if author_el is not None and author_el.text:
            author = author_el.text.strip().removeprefix("/u/").removeprefix("u/")
        if author in ("[deleted]", "[removed]", ""):
            author = "[deleted]"

        cat_el = entry.find(f"{ATOM}category")
        category = cat_el.get("term", "").strip() if cat_el is not None else ""
        subreddit = _subreddit_from(category, url)

        updated_el = entry.find(f"{ATOM}updated")
        updated = (updated_el.text or "").strip() if updated_el is not None else ""

        content_el = entry.find(f"{ATOM}content")
        selftext = ""
        if content_el is not None and content_el.text:
            selftext = re.sub(r"<[^>]+>", " ", content_el.text)
            selftext = re.sub(r"\s+", " ", selftext).strip()[:500]

        relevance = round(token_overlap_relevance(query, title), 3) if query else 0.0

        posts.append(
            {
                "id": "",
                "title": title,
                "url": url,
                "score": 0,
                "num_comments": 0,
                "subreddit": subreddit,
                "created_utc": _iso_to_epoch(updated),
                "author": author,
                "selftext": selftext,
                "date": _iso_to_date(updated),
                "engagement": {
                    "score": 0,
                    "num_comments": 0,
                    "upvote_ratio": None,
                },
                "relevance": relevance,
                "why_relevant": "Reddit RSS",
                "metadata": {},
            }
        )

    return posts


def _build_urls(query: str, depth: str, subreddits: list[str] | None) -> list[str]:
    """Build the keyless RSS feed URLs to fan out across."""
    q = quote_plus(query)
    urls: list[str] = [f"https://www.reddit.com/search.rss?q={q}&sort=relevance&t=month"]
    for raw_sub in subreddits or []:
        sub = raw_sub.removeprefix("r/").strip()
        if not sub:
            continue
        urls.append(
            f"https://www.reddit.com/r/{sub}/search.rss?q={q}&restrict_sr=on&sort=relevance&t=month"
        )
        for sort in LISTING_SORTS.get(depth, LISTING_SORTS["default"]):
            urls.append(f"https://www.reddit.com/r/{sub}/{sort}.rss?t=month")
    return urls


def _fetch_feed(url: str, query: str) -> list[dict[str, Any]]:
    """Fetch and parse one feed. Never raises."""
    try:
        text = client.get_text(url, timeout=FEED_TIMEOUT, accept="application/atom+xml")
        return _parse_feed(text, query) if text else []
    except Exception as e:
        logger.debug("feed fetch failed for %s: %s", url, e)
        return []


def search_rss(
    query: str,
    depth: str = "default",
    subreddits: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Discover Reddit posts for a query via keyless RSS feeds."""
    limit = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"])
    urls = _build_urls(query, depth, subreddits)

    all_posts: list[dict[str, Any]] = []
    workers = min(MAX_WORKERS, len(urls)) or 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_feed, url, query): url for url in urls}
        for future in futures:
            try:
                all_posts.extend(future.result(timeout=FEED_TIMEOUT + 5))
            except (Exception, FuturesTimeoutError) as e:
                logger.debug("feed future failed: %s", e)

    seen: set = set()
    unique: list[dict[str, Any]] = []
    for post in all_posts:
        if post["url"] not in seen:
            seen.add(post["url"])
            unique.append(post)

    for i, post in enumerate(unique):
        post["id"] = f"R{i + 1}"

    return unique[:limit]


# ── Shreddit Helpers ───────────────────────────────────────────────────────


def extract_post_ref(url: str) -> tuple | None:
    """Return (subreddit, post_id) from a Reddit thread URL, or None."""
    m = re.search(r"/r/([^/]+)/comments/([A-Za-z0-9]+)", url or "")
    if not m:
        return None
    return m.group(1), m.group(2)


def _svc_url(subreddit: str, post_id: str) -> str:
    return f"https://www.reddit.com/svc/shreddit/comments/r/{subreddit}/t3_{post_id}?sort=top"


def _attr(tag: str, name: str) -> str:
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return _html.unescape(m.group(1)) if m else ""


def _body_for(html_text: str, thing_id: str) -> str:
    """Extract a comment's text body, anchored on its unique thingId."""
    if not thing_id:
        return ""
    anchor = f'id="{thing_id}-post-rtjson-content"'
    idx = html_text.find(anchor)
    if idx == -1:
        return ""
    window = html_text[idx + len(anchor) : idx + len(anchor) + 8000]
    nxt = _NEXT_RTJSON.search(window)
    if nxt:
        window = window[: nxt.start()]
    paras = _PARA.findall(window)
    if not paras:
        return ""
    text = " ".join(_TAG.sub("", p) for p in paras)
    return _WS.sub(" ", _html.unescape(text)).strip()


def parse_comments(html_text: str, limit: int = MAX_COMMENTS) -> list[dict[str, Any]]:
    """Parse <shreddit-comment> elements into scored comment dicts (sorted desc)."""
    comments: list[dict[str, Any]] = []
    for m in _COMMENT_START.finditer(html_text or ""):
        tag = m.group(0)
        author = _attr(tag, "author") or "[deleted]"
        if author in ("[deleted]", "[removed]"):
            continue
        thing_id = _attr(tag, "thingId")
        body = _body_for(html_text, thing_id)
        if not body or body in ("[deleted]", "[removed]"):
            continue
        try:
            score = int(_attr(tag, "score") or 0)
        except ValueError:
            score = 0
        permalink = _attr(tag, "permalink")
        comments.append(
            {
                "score": score,
                "author": author,
                "body": body[:300],
                "excerpt": body[:200],
                "permalink": permalink,
                "date": _iso_to_date(_attr(tag, "created")),
                "url": f"https://reddit.com{permalink}" if permalink else "",
            }
        )

    comments.sort(key=lambda c: c.get("score", 0), reverse=True)
    return comments[:limit]


def _total_comments(html_text: str) -> int | None:
    m = _TOTAL_COMMENTS.search(html_text or "")
    return int(m.group(1)) if m else None


def fetch_comments(
    post_url: str,
    timeout: int = SVC_TIMEOUT,
) -> dict[str, Any]:
    """Fetch and parse top comments for a Reddit post via the shreddit endpoint."""
    ref = extract_post_ref(post_url)
    if not ref:
        return {"top_comments": [], "comment_insights": [], "num_comments": None}
    sub, post_id = ref

    html_text = client.get_text(_svc_url(sub, post_id), timeout=timeout, accept="text/html")
    if not html_text:
        return {"top_comments": [], "comment_insights": [], "num_comments": None}

    comments = parse_comments(html_text, limit=MAX_COMMENTS)

    insights = []
    for c in comments[:3]:
        if c["excerpt"]:
            insights.append(c["excerpt"])

    return {
        "top_comments": [
            {
                "score": c["score"],
                "date": c["date"],
                "author": c["author"],
                "excerpt": c["excerpt"],
                "url": c["url"],
            }
            for c in comments
        ],
        "comment_insights": insights,
        "num_comments": _total_comments(html_text),
    }
