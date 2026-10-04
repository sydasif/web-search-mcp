"""Digg AI 1000 search via digg-pp-cli (free, no auth required).

Shells out to digg-pp-cli to surface clustered stories curated from ~1000
high-signal AI accounts on X. Each cluster carries a published TLDR, a
curatorial rank, and a list of X posts.

Activation gate: only available when digg-pp-cli is on PATH.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._models import ErrorResponse, SearchResponse
from .._models.types import Depth
from .._utils import format_results_markdown, token_overlap_relevance

logger = logging.getLogger(__name__)

CLI_BIN = "digg-pp-cli"

DEPTH_CONFIG = _ALL_DEPTH_LIMITS.get("digg", {"quick": 8, "default": 20, "deep": 40})
ENRICH_CONFIG = {"quick": 0, "default": 3, "deep": 5}
POSTS_PER_CLUSTER = 5
SEARCH_TIMEOUT = 30
POSTS_TIMEOUT = 15


def _log(msg: str) -> None:
    logger.debug("[Digg] %s", msg)


def is_available() -> bool:
    """True when the digg-pp-cli binary is on PATH."""
    return shutil.which(CLI_BIN) is not None


def _today() -> datetime:
    return datetime.now(UTC)


def _parse_first_post_age(age: str | None, today: datetime | None = None) -> str | None:
    """Convert a digg firstPostAge token (e.g. '5d', '17d', '5h', '1w', '1m')
    into a YYYY-MM-DD string. Returns None when outside the last-30-day window."""
    if not age or not isinstance(age, str):
        return None
    age = age.strip().lower()
    if len(age) < 2:
        return None
    unit = age[-1]
    try:
        amount = int(age[:-1])
    except (ValueError, TypeError):
        return None
    if amount < 0:
        return None

    base = today or _today()

    if unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    elif unit == "w":
        delta = timedelta(weeks=amount)
    elif unit == "m":
        delta = timedelta(days=amount * 30)
    else:
        return None

    if delta > timedelta(days=30):
        return None

    point = base - delta
    return point.date().isoformat()


def _build_search_args(query: str, limit: int) -> list[str]:
    return [
        CLI_BIN,
        "search",
        query,
        "--since",
        "30d",
        "--agent",
        "--limit",
        str(limit),
    ]


def _build_posts_args(cluster_url_id: str, posts_per: int) -> list[str]:
    return [
        CLI_BIN,
        "posts",
        cluster_url_id,
        "--agent",
        "--by",
        "rank",
        "--limit",
        str(posts_per),
    ]


def _run_cli(cmd: list[str], timeout: int) -> dict[str, Any]:
    """Invoke digg-pp-cli and parse the JSON envelope. Never raises."""
    if not is_available():
        return {"results": [], "error": f"{CLI_BIN} not on PATH"}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        _log(f"Timeout: {exc}")
        return {"results": [], "error": str(exc)}
    except FileNotFoundError as exc:
        _log(f"Binary missing: {exc}")
        return {"results": [], "error": str(exc)}
    except OSError as exc:
        _log(f"Spawn failed: {exc}")
        return {"results": [], "error": str(exc)}

    if result.returncode != 0:
        snippet = (result.stderr or "").strip().splitlines()[:1]
        first = snippet[0] if snippet else f"exit {result.returncode}"
        _log(f"CLI exit {result.returncode}: {first}")
        return {"results": [], "error": first}

    stdout = result.stdout or ""
    if not stdout.strip():
        return {"results": []}
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        _log(f"JSON decode failed: {exc}")
        return {"results": [], "error": f"json decode: {exc}"}

    if not isinstance(data, dict):
        return {"results": []}
    results = data.get("results")
    if not isinstance(results, list):
        return {"results": []}
    return data


def _build_url(cluster_url_id: str) -> str:
    return f"https://di.gg/ai/{cluster_url_id}"


def _rank_score(rank: int | None) -> float:
    """Convert Digg rank (lower is better, top 50 are notable) into a
    positive engagement-style signal in [0, 50]."""
    if rank is None:
        return 0.0
    try:
        r = int(rank)
    except (TypeError, ValueError):
        return 0.0
    if r < 1 or r > 50:
        return 0.0
    return float(51 - r)


def search_digg(
    topic: str,
    from_date: str,
    to_date: str,
    depth: Depth = "default",
) -> dict[str, Any]:
    """Search Digg AI 1000 clusters via digg-pp-cli."""
    limit = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    if not topic or not topic.strip():
        return {"results": []}
    cmd = _build_search_args(topic, limit)
    _log(f"search '{topic}' (limit={limit}, since=30d)")
    response = _run_cli(cmd, timeout=SEARCH_TIMEOUT)
    n = len(response.get("results") or [])
    _log(f"found {n} clusters")
    return response


def parse_digg_response(
    response: dict[str, Any],
    query: str = "",
) -> list[dict[str, Any]]:
    """Parse a digg search envelope into normalized item dicts."""
    raw = response.get("results") if isinstance(response, dict) else None
    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    for i, cluster in enumerate(raw):
        if not isinstance(cluster, dict):
            continue
        cluster_url_id = cluster.get("clusterUrlId")
        if not cluster_url_id:
            continue

        title = str(cluster.get("title") or "").strip()
        tldr = str(cluster.get("tldr") or "").strip()
        rank = cluster.get("rank")
        post_count = cluster.get("postCount") or 0
        unique_authors = cluster.get("uniqueAuthors") or 0
        first_post_age = cluster.get("firstPostAge")
        date_str = _parse_first_post_age(first_post_age)
        if date_str is None and first_post_age:
            continue

        rank_decay = max(0.3, 1.0 - (i * 0.02))
        content_score = token_overlap_relevance(query, f"{title} {tldr}".strip()) if query else 0.5
        rank_boost = min(0.2, _rank_score(rank) / 250.0)
        relevance = min(1.0, 0.55 * rank_decay + 0.35 * content_score + rank_boost)

        items.append(
            {
                "id": str(cluster_url_id),
                "title": title or f"Digg cluster {i + 1}",
                "url": _build_url(str(cluster_url_id)),
                "tldr": tldr,
                "author": "",
                "date": date_str,
                "engagement": {
                    "postCount": int(post_count) if isinstance(post_count, (int, float)) else 0,
                    "uniqueAuthors": int(unique_authors)
                    if isinstance(unique_authors, (int, float))
                    else 0,
                    "rank": int(rank) if isinstance(rank, (int, float)) else None,
                    "rank_score": _rank_score(rank),
                },
                "first_post_age": first_post_age,
                "posts": [],
                "relevance": round(relevance, 2),
                "why_relevant": (
                    f"Digg cluster (rank {rank}, {post_count} posts, {unique_authors} authors)"
                    if rank is not None
                    else f"Digg cluster ({post_count} posts, {unique_authors} authors)"
                ),
            }
        )

    return items


def _is_safe_http_url(url: str) -> bool:
    """True iff url parses with an http or https scheme."""
    try:
        from urllib.parse import urlparse

        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False
    return scheme in ("http", "https")


def _parse_post(raw_post: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce a digg post payload into the small dict render uses."""
    if not isinstance(raw_post, dict):
        return None
    body = str(raw_post.get("body") or "").strip()
    if not body:
        return None
    author = raw_post.get("author") or {}
    if not isinstance(author, dict):
        author = {}
    username = str(author.get("username") or "").strip()
    if not username:
        return None
    x_url = str(raw_post.get("xUrl") or "").strip()
    if not x_url:
        return None
    if not _is_safe_http_url(x_url):
        logger.warning("dropped post with unsafe xUrl scheme: %r", x_url)
        return None
    return {
        "username": username,
        "display_name": str(author.get("display_name") or "").strip() or username,
        "category": str(author.get("category") or "").strip(),
        "rank": author.get("rank"),
        "body": body,
        "post_type": str(raw_post.get("post_type") or "tweet").strip(),
        "x_url": x_url,
        "posted_at": raw_post.get("posted_at"),
    }


def fetch_top_posts(
    cluster_url_id: str, posts_per: int = POSTS_PER_CLUSTER
) -> list[dict[str, Any]]:
    """Fetch top-ranked X posts attached to a cluster. Returns [] on failure."""
    cmd = _build_posts_args(cluster_url_id, posts_per)
    response = _run_cli(cmd, timeout=POSTS_TIMEOUT)
    raw = response.get("results") if isinstance(response, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for rp in raw:
        parsed = _parse_post(rp)
        if parsed:
            out.append(parsed)
    return out


def enrich_digg_clusters(
    items: list[dict[str, Any]],
    depth: Depth = "default",
) -> list[dict[str, Any]]:
    """Enrich top clusters with their X posts."""
    enrich_limit = ENRICH_CONFIG.get(depth, ENRICH_CONFIG["default"])
    for item in items[:enrich_limit]:
        cluster_url_id = item.get("id")
        if cluster_url_id:
            posts = fetch_top_posts(cluster_url_id)
            item["posts"] = posts
    return items


def format_digg_markdown(items: list[dict[str, Any]], query: str) -> str:
    """Format Digg results as markdown."""

    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        rank = item.get("engagement", {}).get("rank")
        rank_str = f" (rank #{rank})" if rank else ""
        post_count = item.get("engagement", {}).get("postCount", 0)
        authors = item.get("engagement", {}).get("uniqueAuthors", 0)
        lines = [
            f"{i}. **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**{rank_str}",
            f"   {post_count} posts, {authors} authors",
        ]
        tldr = item.get("tldr", "")
        if tldr:
            lines.append(f"   {tldr[:300]}...")
        if item.get("posts"):
            lines.append("   Top X posts:")
            for p in item["posts"][:2]:
                lines.append(f"   > @{p.get('username', 'unknown')}: {p.get('body', '')[:150]}...")
        return lines

    return format_results_markdown(items, query, "Digg AI 1000", "clusters", _item_lines)


def digg_search_tool(
    query: str,
    max_results: int = 20,
    time_range: str | None = None,
    depth: Depth = "default",
    response_format: str = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Digg AI 1000 — free, no API key needed.

    Requires digg-pp-cli on PATH (install via:
    npx -y @mvanhorn/printing-press-library install digg --cli-only)
    """
    if not query or not query.strip():
        return ErrorResponse(
            error="Query cannot be empty", details="Provide a non-empty search query."
        )

    if not is_available():
        return ErrorResponse(
            error="Digg search unavailable",
            details=(
                "digg-pp-cli not found on PATH. Install with: "
                "npx -y @mvanhorn/printing-press-library install digg --cli-only"
            ),
        )

    from datetime import datetime, timedelta

    today = datetime.now().date()
    from_date = "2000-01-01"
    to_date = today.isoformat()

    if time_range:
        if time_range == "d":
            from_date = (today - timedelta(days=1)).isoformat()
        elif time_range == "w":
            from_date = (today - timedelta(weeks=1)).isoformat()
        elif time_range == "m":
            from_date = (today - timedelta(weeks=4)).isoformat()
        elif time_range == "y":
            from_date = (today - timedelta(weeks=52)).isoformat()

    depth_limits = _ALL_DEPTH_LIMITS.get("digg", {"quick": 8, "default": 20, "deep": 40})
    max_results = min(max_results, depth_limits.get(depth, 20))

    try:
        response = search_digg(query, from_date, to_date, depth)
        items = parse_digg_response(response, query)
        items = enrich_digg_clusters(items, depth)
        items = items[:max_results]

        if response_format == "markdown":
            return format_digg_markdown(items, query)

        from .._models import SearchResult, build_search_response

        results = []
        for item in items:
            body_parts = []
            if item.get("title"):
                body_parts.append(item["title"])
            if item.get("tldr"):
                body_parts.append(item["tldr"])
            if item.get("posts"):
                posts_text = " | ".join(p.get("body", "")[:100] for p in item["posts"][:3])
                body_parts.append(f"Posts: {posts_text}")
            results.append(
                SearchResult(
                    title=item.get("title", "Digg cluster"),
                    href=item.get("url", ""),
                    url=item.get("url", ""),
                    body=" ".join(body_parts) if body_parts else None,
                )
            )
        return build_search_response(results, query)

    except Exception as e:
        logger.exception("Digg search failed for query %r", query)
        return ErrorResponse(error="Digg search failed", details=str(e))
