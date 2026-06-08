"""Legacy Reddit .json search — demoted tier, often returns 403.

Kept as a one-shot fallback: residential IPs may still get 200, so it's worth
one cheap try before falling back to RSS. Never raises on failure — returns []
so the pipeline falls through to the keyless path.
"""

import sys
from typing import Any, Dict, List
from urllib.parse import quote_plus

from . import reddit_http
from .utils import token_overlap_relevance


def _log(msg: str) -> None:
    sys.stderr.write(f"[RedditPublic] {msg}\n")
    sys.stderr.flush()


DEPTH_LIMITS = {
    "quick": 10,
    "default": 25,
    "deep": 50,
}


def _parse_posts(data: Dict[str, Any], query: str = "") -> List[Dict[str, Any]]:
    """Parse Reddit .json response into normalized post dicts."""
    posts: List[Dict[str, Any]] = []
    try:
        children = data.get("data", {}).get("children", [])
        for child in children:
            d = child.get("data", {})
            if not d.get("permalink"):
                continue

            title = d.get("title", "")
            url = f"https://www.reddit.com{d.get('permalink', '')}"
            score = d.get("score", 0)
            num_comments = d.get("num_comments", 0)
            subreddit = d.get("subreddit", "")
            created_utc = d.get("created_utc", 0)
            author = d.get("author", "[deleted]")
            selftext = d.get("selftext", "")[:500]

            from datetime import datetime, timezone

            created_dt = (
                datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None
            )
            date_str = created_dt.date().isoformat() if created_dt else None

            relevance = round(token_overlap_relevance(query, title), 3) if query else 0.0

            posts.append(
                {
                    "id": d.get("id", ""),
                    "title": title,
                    "url": url,
                    "score": score,
                    "num_comments": num_comments,
                    "subreddit": subreddit,
                    "created_utc": created_utc,
                    "author": author,
                    "selftext": selftext,
                    "date": date_str,
                    "engagement": {
                        "score": score,
                        "num_comments": num_comments,
                        "upvote_ratio": d.get("upvote_ratio"),
                    },
                    "relevance": relevance,
                    "why_relevant": "Reddit .json",
                    "metadata": {"post_id": d.get("id", "")},
                }
            )
    except Exception as e:
        _log(f"parse error: {e}")
    return posts


def search(topic: str, depth: str = "default") -> List[Dict[str, Any]]:
    """One-shot global .json search. Returns [] on any failure (403, timeout, etc.)."""
    limit = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"])
    q = quote_plus(topic)
    url = f"https://www.reddit.com/search.json?q={q}&limit={limit}&sort=relevance&t=month"

    headers = {
        "User-Agent": "web-search-mcp/1.0 (Reddit Search)",
        "Accept": "application/json",
    }

    try:
        data = reddit_http.get(url, headers=headers, timeout=15, retries=1)
        return _parse_posts(data, topic)
    except Exception as e:
        _log(f"search failed: {e}")
        return []
