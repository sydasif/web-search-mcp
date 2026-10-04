"""Arctic-Shift score resolver — post upvote counts by id, keyless and free.

Uses https://arctic-shift.photon-reddit.com/api/posts/ids to get post scores
and comment counts for Reddit post IDs. Best-effort, never raises.
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime
from typing import Any

from ..._http import get_json_client

API = "https://arctic-shift.photon-reddit.com/api/posts/ids"
SEARCH_API = "https://arctic-shift.photon-reddit.com/api/posts/search"
BATCH = 50  # ids per request
TIMEOUT = 15
MAX_BATCHES = 3  # cap total requests per run
PACE_SECONDS = 0.4  # gap between batches
LISTING_DEPTH_LIMITS = {"quick": 10, "default": 25, "deep": 50}
LISTING_SUPPLEMENT_MULTIPLIER = 2
LISTING_DEADLINE_SECONDS = 45

# In-run memo: base36 id -> {score, num_comments}
_cache: dict[str, dict[str, int]] = {}


def _log(msg: str) -> None:
    sys.stderr.write(f"[ArcticShift] {msg}\n")
    sys.stderr.flush()


def _epoch_to_date(value: Any) -> str | None:
    """Epoch seconds -> YYYY-MM-DD (UTC), or None on garbage."""
    try:
        return datetime.fromtimestamp(int(value), tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def fetch_scores(post_ids: list[str]) -> dict[str, dict[str, int]]:
    """Return {base36_post_id: {"score", "num_comments"}} for the given ids.

    Batched, paced, in-run cached, and never raises. Ids that fail or are absent
    from the archive are simply missing from the result.
    """
    out: dict[str, dict[str, int]] = {}
    todo: list[str] = []
    for pid in post_ids:
        if not pid:
            continue
        if pid in _cache:
            out[pid] = _cache[pid]
        elif pid not in todo:
            todo.append(pid)

    batches = [todo[i : i + BATCH] for i in range(0, len(todo), BATCH)][:MAX_BATCHES]
    for n, batch in enumerate(batches):
        if n:
            time.sleep(PACE_SECONDS)
        try:
            with get_json_client(timeout=TIMEOUT) as client:
                response = client.get(
                    f"{API}?ids={','.join(batch)}",
                    headers={"User-Agent": "web-search-mcp/1.0"},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            _log(f"lookup failed ({e}); {len(batch)} ids left unscored")
            break
        rows = (data or {}).get("data")
        if not isinstance(rows, list):
            _log(f"unexpected response (rate-limited?): {str(data)[:80]}")
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id") or "").removeprefix("t3_")
            if not rid:
                continue
            try:
                entry = {
                    "score": int(row.get("score") or 0),
                    "num_comments": int(row.get("num_comments") or 0),
                }
            except (TypeError, ValueError):
                continue
            _cache[rid] = entry
            out[rid] = entry
    return out


def _normalize_listing_row(row: dict[str, Any], query: str = "") -> dict[str, Any]:
    """Normalize an arctic-shift post row to match the shreddit card schema."""
    from ..._utils import token_overlap_relevance

    pid = str(row.get("id") or "").removeprefix("t3_")
    permalink = row.get("permalink") or ""
    title = row.get("title") or ""
    try:
        score = int(row.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    try:
        num_comments = int(row.get("num_comments") or 0)
    except (TypeError, ValueError):
        num_comments = 0
    author = row.get("author") or "[deleted]"
    if author in ("[deleted]", "[removed]"):
        author = "[deleted]"
    url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else (permalink or "")
    return {
        "id": "",
        "title": title,
        "url": url,
        "score": score,
        "num_comments": num_comments,
        "subreddit": row.get("subreddit") or "",
        "created_utc": row.get("created_utc"),
        "author": author,
        "selftext": row.get("selftext") or "",
        "date": _epoch_to_date(row.get("created_utc")),
        "engagement": {"score": score, "num_comments": num_comments, "upvote_ratio": None},
        "relevance": round(token_overlap_relevance(query, title), 3) if query else 0.0,
        "why_relevant": "Reddit listing (arctic-shift)",
        "metadata": {"post_id": pid},
    }


def fetch_listings(
    subreddits: list[str],
    depth: str = "default",
    query: str = "",
    sorts: list[str] | None = None,
    timeframe: str = "month",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Scored subreddit listings from the arctic-shift archive, keyless.

    Drop-in fallback/supplement for shreddit partials. Arctic-shift has no
    top/hot/new lanes, only recency. When sorts contains multiple entries,
    we fetch more posts per subreddit to partially compensate.

    Best-effort, never raises: returns [] on any failure.
    """
    if not subreddits:
        return []
    base = limit or LISTING_DEPTH_LIMITS.get(depth, LISTING_DEPTH_LIMITS["default"])
    n = base * LISTING_SUPPLEMENT_MULTIPLIER if sorts and len(sorts) > 1 else base
    out: list[dict[str, Any]] = []
    deadline = time.time() + LISTING_DEADLINE_SECONDS
    fetched_count = 0
    for sub in subreddits:
        if time.time() >= deadline:
            _log(f"listing deadline reached after {fetched_count} subs; skipping remaining")
            break
        sub = sub.removeprefix("r/").strip()
        if not sub or sub.lower() == "all":
            continue
        if fetched_count:
            time.sleep(PACE_SECONDS)
        fetched_count += 1
        try:
            with get_json_client(timeout=TIMEOUT) as client:
                response = client.get(
                    f"{SEARCH_API}?subreddit={sub}&limit={n}&sort=desc",
                    headers={"User-Agent": "web-search-mcp/1.0"},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            _log(f"listing search failed r/{sub}: {e}")
            continue
        rows = (data or {}).get("data")
        if not isinstance(rows, list):
            _log(f"unexpected listing response for r/{sub}: {str(data)[:80]}")
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            post = _normalize_listing_row(row, query)
            if post["url"]:
                out.append(post)

    seen: set = set()
    unique: list[dict[str, Any]] = []
    for p in out:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    return unique
