"""X/Twitter search via Xquik or vendored Bird CLI.

Uses the vendored bird-search.mjs (MIT, @steipete/bird v0.8.0) to query
Twitter's GraphQL API directly. No API key needed, just two cookies from
a logged-in X session. If XQUIK_API_KEY is set, searches use Xquik instead.

Authentication:
    Set XQUIK_API_KEY for Xquik. Otherwise set AUTH_TOKEN and CT0 environment
    variables. Extract cookies from your browser after logging in to x.com.
    These are session cookies that expire periodically - refresh them when
    searches start failing.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

import httpx

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._http import get_json_client
from .._models.types import Depth
from .._utils import format_results_markdown

logger = logging.getLogger(__name__)

# Path to vendored bird-search
_BIRD_SEARCH_MJS = Path(__file__).parent.parent / "vendor" / "bird-search" / "bird-search.mjs"
_XQUIK_SEARCH_URL = "https://xquik.com/api/v1/x/tweets/search"

# Depth configurations: number of results to request
DEPTH_CONFIG = _ALL_DEPTH_LIMITS["x"]

_TIMEOUT_SECS = {
    "quick": 30,
    "default": 45,
    "deep": 60,
}


def is_available() -> bool:
    """Check if Bird CLI is available and Node.js is installed."""
    if not _BIRD_SEARCH_MJS.exists():
        logger.warning("bird-search.mjs not found at %s", _BIRD_SEARCH_MJS)
        return False
    if shutil.which("node") is None:
        logger.warning("Node.js not found on PATH")
        return False
    return True


def is_authenticated() -> bool:
    """Check if X credentials are available in environment."""
    return bool(os.environ.get("AUTH_TOKEN")) and bool(os.environ.get("CT0"))


def _xquik_api_key() -> str:
    """Return the configured Xquik API key, if present."""
    return os.environ.get("XQUIK_API_KEY", "").strip()


def _build_env() -> dict[str, str]:
    """Build environment dict for the Node subprocess."""
    env = os.environ.copy()
    env["BIRD_DISABLE_BROWSER_COOKIES"] = "1"
    return env


def _sanitize_query(query: str) -> str:
    """Strip control characters from a query string for safe subprocess use."""
    return "".join(ch for ch in query if ch >= " " or ch in "\t\n\r")


def _run_bird_search(query: str, count: int, timeout: int) -> dict[str, Any]:
    """Run a single bird-search subprocess and return parsed JSON."""
    cmd = [
        "node",
        str(_BIRD_SEARCH_MJS),
        _sanitize_query(query),
        "--count",
        str(count),
        "--json",
    ]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
    except subprocess.TimeoutExpired:
        logger.warning("X search timed out after %ds for query: %s", timeout, query)
        return {"error": f"Search timed out after {timeout}s", "items": []}
    except FileNotFoundError as e:
        logger.exception("X search failed - node not found")
        return {"error": f"Node.js not found: {e}", "items": []}
    except Exception as e:
        logger.exception("X search subprocess error")
        return {"error": str(e), "items": []}

    if result.returncode != 0:
        stderr = result.stderr.strip()
        logger.warning("bird-search exited %d: %s", result.returncode, stderr)
        return {"error": stderr or "Bird search failed", "items": []}

    output = result.stdout.strip()
    if not output:
        return {"items": []}

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as e:
        logger.warning(
            "bird-search returned non-JSON (first 80 chars): %s ...",
            output[:80],
        )
        return {"error": f"Invalid JSON response: {e}", "items": []}

    if isinstance(parsed, list):
        return {"items": parsed}
    return parsed


def _extract_xquik_items(payload: Any) -> list[Any]:
    """Extract tweet arrays from common Xquik response envelopes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("tweets", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("tweets", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _run_xquik_search(query: str, count: int, timeout: int) -> dict[str, Any]:
    """Run a single Xquik search request and return a normalized item envelope."""
    api_key = _xquik_api_key()
    if not api_key:
        return {"items": []}

    try:
        with get_json_client(timeout=timeout) as client:
            response = client.get(
                _XQUIK_SEARCH_URL,
                params={"q": query, "queryType": "Latest", "limit": str(count)},
                headers={"x-api-key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Xquik X search returned HTTP %d", e.response.status_code)
        return {"error": f"Xquik X search returned HTTP {e.response.status_code}", "items": []}
    except (httpx.RequestError, ValueError) as e:
        logger.warning("Xquik X search failed: %s", e)
        return {"error": str(e), "items": []}

    return {"items": _extract_xquik_items(payload)}


class TweetItem(TypedDict):
    """Normalized tweet dict returned by search_x."""

    id: str
    text: str
    url: str
    author_handle: str
    date: NotRequired[str | None]
    engagement: NotRequired[dict[str, int]]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    """Return dict values as-is and coerce all other values to an empty dict."""
    if isinstance(value, dict):
        return value
    return {}


def _first_string(*values: Any) -> str:
    """Return the first non-empty string from a candidate list."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_item(tweet: Any, index: int, query: str) -> TweetItem | None:
    """Parse a single tweet dict into a normalized item."""
    if not isinstance(tweet, dict):
        return None

    author = _dict_or_empty(tweet.get("author") or tweet.get("user"))
    screen_name = _first_string(
        author.get("username"),
        author.get("screen_name"),
        tweet.get("author_handle"),
        tweet.get("authorUsername"),
        tweet.get("author_screen_name"),
    )

    # Extract URL
    url = tweet.get("permanent_url") or tweet.get("url", "")
    if not url and tweet.get("id") and screen_name:
        url = f"https://x.com/{screen_name}/status/{tweet['id']}"
    if not url:
        return None

    # Parse date
    date = None
    created_at = (
        tweet.get("createdAt")
        or tweet.get("created_at")
        or tweet.get("publishedAt")
        or tweet.get("published_at")
        or ""
    )
    if created_at:
        try:
            if len(created_at) > 10 and created_at[10] == "T":
                dt = datetime.fromisoformat(created_at)
            else:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            date = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    # User info
    author_handle = screen_name

    # Engagement
    engagement = {
        "likes": _safe_int(
            tweet.get("likeCount") or tweet.get("like_count") or tweet.get("favorite_count"),
        ),
        "retweets": _safe_int(tweet.get("retweetCount") or tweet.get("retweet_count")),
        "replies": _safe_int(tweet.get("replyCount") or tweet.get("reply_count")),
        "quotes": _safe_int(tweet.get("quoteCount") or tweet.get("quote_count")),
        "views": _safe_int(tweet.get("viewCount") or tweet.get("view_count")),
        "bookmarks": _safe_int(tweet.get("bookmarkCount") or tweet.get("bookmark_count")),
    }
    # Remove None values
    engagement = {k: v for k, v in engagement.items() if v is not None}

    text = str(
        tweet.get("text")
        or tweet.get("full_text")
        or tweet.get("fullText")
        or tweet.get("content")
        or "",
    ).strip()[:500]

    return cast(
        "TweetItem",
        {
            "id": f"X{index + 1}",
            "text": text,
            "url": url,
            "author_handle": author_handle.lstrip("@"),
            "date": date,
            "engagement": engagement,
        },
    )


def _safe_int(val: Any) -> int | None:
    """Convert value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def search_x(
    query: str,
    from_date: str | None = None,
    depth: Depth = "default",
) -> list[TweetItem]:
    """Search X/Twitter using Xquik when configured, otherwise the vendored Bird CLI.

    Args:
        query: Search query string
        from_date: Optional start date (YYYY-MM-DD). Defaults to 30 days ago.
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of normalized tweet dicts with text, url, author_handle, date, engagement.

    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    timeout = _TIMEOUT_SECS.get(depth, _TIMEOUT_SECS["default"])

    # Build query with date filter
    search_query = query
    if from_date:
        search_query = f"{query} since:{from_date}"

    logger.info("X searching '%s' (depth=%s, count=%d)", query, depth, count)

    if _xquik_api_key():
        response = _run_xquik_search(search_query, count, timeout)
    else:
        if not is_available():
            return [
                {
                    "id": "XERR",
                    "text": "X search unavailable: bird-search.mjs not found or Node.js missing",
                    "url": "",
                    "author_handle": "",
                },
            ]

        if not is_authenticated():
            return [
                {
                    "id": "XERR",
                    "text": (
                        "X search requires AUTH_TOKEN and CT0 environment variables."
                        " Extract these from your browser cookies after logging"
                        " into x.com."
                    ),
                    "url": "",
                    "author_handle": "",
                },
            ]

        response = _run_bird_search(search_query, count, timeout)

    items = response.get("items", [])
    if not isinstance(items, list):
        items = []

    # Parse items
    parsed = []
    for i, tweet in enumerate(items):
        item = _parse_item(tweet, i, query)
        if item:
            parsed.append(item)

    logger.info("X search returned %d items", len(parsed))
    return parsed[: DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])]


def format_x_markdown(items: list[TweetItem], query: str) -> str:
    """Format X results as markdown."""
    # Check for error items (unique to X tool)
    if len(items) == 1 and items[0].get("id") == "XERR":
        return f"\u26a0\ufe0f {items[0]['text']}"

    def _item_lines(item: dict, i: int) -> list[str]:
        handle = item.get("author_handle", "unknown")
        url = item.get("url", "#")
        text = (item.get("text", "") or "")[:200]
        lines = [
            f"{i}. **@{handle}** \u00b7 [{url}]({url})",
            f"   {text}{'...' if len(item.get('text', '') or '') > 200 else ''}",
        ]
        eng = item.get("engagement", {}) or {}
        eng_parts = []
        if eng.get("likes"):
            eng_parts.append(f"\u2764\ufe0f {eng['likes']}")
        if eng.get("retweets"):
            eng_parts.append(f"\U0001f501 {eng['retweets']}")
        if eng.get("replies"):
            eng_parts.append(f"\U0001f4ac {eng['replies']}")
        if eng_parts:
            lines.append(f"   {' '.join(eng_parts)}")
        if item.get("date"):
            lines.append(f"   {item['date']}")
        return lines

    return format_results_markdown(
        cast("list[dict[str, Any]]", items), query, "X/Twitter", "posts", _item_lines
    )
