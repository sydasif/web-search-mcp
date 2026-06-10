"""X/Twitter search via vendored Bird CLI — requires AUTH_TOKEN + CT0 cookies.

Uses the vendored bird-search.mjs (MIT, @steipete/bird v0.8.0) to query
Twitter's GraphQL API directly. No API key needed, just two cookies from
a logged-in X session.

Authentication:
    Set AUTH_TOKEN and CT0 environment variables. Extract these from your
    browser's cookies after logging in to x.com. These are session cookies
    that expire periodically — refresh them when searches start failing.
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to vendored bird-search
_BIRD_SEARCH_MJS = Path(__file__).parent / "vendor" / "bird-search" / "bird-search.mjs"

# Depth configurations: number of results to request
DEPTH_CONFIG = {
    "quick": 12,
    "default": 30,
    "deep": 60,
}

RESULT_CAP = {
    "quick": 12,
    "default": 30,
    "deep": 60,
}

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


def _build_env() -> dict[str, str]:
    """Build environment dict for the Node subprocess."""
    env = os.environ.copy()
    env["BIRD_DISABLE_BROWSER_COOKIES"] = "1"
    return env


def _run_bird_search(query: str, count: int, timeout: int) -> dict[str, Any]:
    """Run a single bird-search subprocess and return parsed JSON."""
    cmd = [
        "node",
        str(_BIRD_SEARCH_MJS),
        query,
        "--count",
        str(count),
        "--json",
    ]

    try:
        result = subprocess.run(
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
        logger.error("X search failed — node not found: %s", e)
        return {"error": f"Node.js not found: {e}", "items": []}
    except Exception as e:
        logger.error("X search subprocess error: %s", e)
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


def _parse_item(tweet: dict, index: int, query: str) -> dict | None:
    """Parse a single tweet dict into a normalized item."""
    if not isinstance(tweet, dict):
        return None

    # Extract URL
    url = tweet.get("permanent_url") or tweet.get("url", "")
    if not url and tweet.get("id"):
        author = tweet.get("author", {}) or tweet.get("user", {})
        screen_name = author.get("username") or author.get("screen_name", "")
        if screen_name:
            url = f"https://x.com/{screen_name}/status/{tweet['id']}"
    if not url:
        return None

    # Parse date
    date = None
    created_at = tweet.get("createdAt") or tweet.get("created_at", "")
    if created_at:
        try:
            if len(created_at) > 10 and created_at[10] == "T":
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            date = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    # User info
    author = tweet.get("author", {}) or tweet.get("user", {})
    author_handle = (
        author.get("username") or author.get("screen_name", "") or tweet.get("author_handle", "")
    )

    # Engagement
    engagement = {
        "likes": _safe_int(
            tweet.get("likeCount") or tweet.get("like_count") or tweet.get("favorite_count")
        ),
        "retweets": _safe_int(tweet.get("retweetCount") or tweet.get("retweet_count")),
        "replies": _safe_int(tweet.get("replyCount") or tweet.get("reply_count")),
        "quotes": _safe_int(tweet.get("quoteCount") or tweet.get("quote_count")),
        "views": _safe_int(tweet.get("viewCount") or tweet.get("view_count")),
        "bookmarks": _safe_int(tweet.get("bookmarkCount") or tweet.get("bookmark_count")),
    }
    # Remove None values
    engagement = {k: v for k, v in engagement.items() if v is not None}
    if not engagement:
        engagement = {}

    text = str(tweet.get("text", tweet.get("full_text", ""))).strip()[:500]

    return {
        "id": f"X{index + 1}",
        "text": text,
        "url": url,
        "author_handle": author_handle.lstrip("@"),
        "date": date,
        "engagement": engagement,
    }


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
    depth: str = "default",
) -> list[dict]:
    """Search X/Twitter using the vendored Bird CLI.

    Args:
        query: Search query string
        from_date: Optional start date (YYYY-MM-DD). Defaults to 30 days ago.
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of normalized tweet dicts with text, url, author_handle, date, engagement.
    """
    if not is_available():
        return [
            {
                "error": "X search unavailable: bird-search.mjs not found or Node.js missing",
            }
        ]

    if not is_authenticated():
        return [
            {
                "error": "X search requires AUTH_TOKEN and CT0 environment variables. "
                "Extract these from your browser cookies after logging into x.com.",
            }
        ]

    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    timeout = _TIMEOUT_SECS.get(depth, _TIMEOUT_SECS["default"])

    # Build query with date filter
    search_query = query
    if from_date:
        search_query = f"{query} since:{from_date}"

    logger.info("X searching '%s' (depth=%s, count=%d)", query, depth, count)

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
    return parsed[: RESULT_CAP.get(depth, RESULT_CAP["default"])]
