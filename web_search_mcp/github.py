"""GitHub Issues/PRs search via the public GitHub Search API.

Uses api.github.com/search/issues for issue/PR discovery and
per-item comment enrichment. Auth via GITHUB_TOKEN env var or
`gh auth token` subprocess fallback.
"""

import logging
import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("web-search-mcp")

SEARCH_URL = "https://api.github.com/search/issues"
REPO_API = "https://api.github.com/repos"

DEPTH_LIMITS = {"quick": 15, "default": 30, "deep": 60}
ENRICH_LIMITS = {"quick": 3, "default": 5, "deep": 8}

USER_AGENT = "web-search-mcp/1.0"
MAX_WORKERS = 5
TIMEOUT = 30


def _resolve_token(token: str | None = None) -> str | None:
    """Resolve GitHub auth token from argument, env, or gh CLI."""
    if token:
        return token
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token
    # Fallback: try gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _fetch_json(
    url: str,
    token: str | None = None,
    timeout: int = 15,
) -> dict | list | None:
    """Fetch JSON from GitHub API. Returns None on failure."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.warning("GitHub 403 rate limited or forbidden: %s", url)
            return None
        if e.response.status_code == 422:
            logger.warning("GitHub 422 unprocessable: %s", url)
            return None
        logger.warning("GitHub HTTP %d: %s", e.response.status_code, url)
        return None
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("GitHub network error: %s", e)
        return None


def _parse_repo_from_url(html_url: str) -> str:
    """Extract 'owner/repo' from a GitHub issue/PR URL."""
    parts = html_url.replace("https://github.com/", "").split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _parse_date(iso_str: str | None) -> str | None:
    """Parse GitHub ISO 8601 datetime to YYYY-MM-DD."""
    if not iso_str:
        return None
    try:
        return iso_str[:10]
    except (IndexError, TypeError):
        return None


def _compute_relevance(
    query: str,
    title: str,
    rank_index: int,
    reactions: int,
    comments: int,
) -> float:
    """Blend text relevance with engagement signals."""
    rank_score = max(0.3, 1.0 - (rank_index * 0.02))
    engagement_boost = min(0.2, math.log1p(reactions + comments) / 20)

    if query:
        q_tokens = set(query.lower().split())
        t_tokens = set(title.lower().split())
        overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
        content_score = min(1.0, overlap * 2)
        relevance = min(1.0, 0.6 * rank_score + 0.4 * content_score + engagement_boost)
    else:
        relevance = min(1.0, rank_score * 0.7 + engagement_boost + 0.1)

    return round(relevance, 2)


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


def search_github(
    topic: str,
    depth: str = "default",
    token: str | None = None,
) -> list[dict]:
    """Search GitHub Issues and PRs via the GitHub Search API.

    Args:
        topic: Search topic
        depth: 'quick', 'default', or 'deep'
        token: Optional GitHub token (falls back to env/gh CLI)

    Returns:
        List of normalized item dicts ready for pipeline use.
    """
    count = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["default"])
    resolved_token = _resolve_token(token)

    if not resolved_token:
        logger.warning("No GitHub token available (set GITHUB_TOKEN or install gh CLI)")
        return []

    logger.info("GitHub searching for '%s' (count=%d)", topic, count)

    q = f"{topic} in:title"
    params: dict[str, str] = {
        "q": q,
        "sort": "reactions",
        "order": "desc",
        "per_page": str(min(count, 100)),
    }
    url = f"{SEARCH_URL}?{urlencode(params)}"

    data = _fetch_json(url, token=resolved_token, timeout=TIMEOUT)
    if not data or not isinstance(data, dict):
        return []

    raw_items = data.get("items", [])
    logger.info("GitHub found %d issues/PRs", len(raw_items))

    return _parse_items(raw_items, topic, count)


def _parse_items(
    raw_items: list[dict],
    topic: str,
    count: int,
) -> list[dict]:
    """Normalize raw GitHub API items into standard item dicts."""
    items: list[dict] = []
    for i, item in enumerate(raw_items[:count]):
        html_url = item.get("html_url", "")
        repo = _parse_repo_from_url(html_url)
        title = item.get("title", "")
        body_text = item.get("body") or ""
        reactions_total = (
            item.get("reactions", {}).get("total_count", 0)
            if isinstance(item.get("reactions"), dict)
            else 0
        )
        comment_count = item.get("comments", 0)
        labels = [
            lbl.get("name", "") for lbl in (item.get("labels") or []) if isinstance(lbl, dict)
        ]
        state = item.get("state", "")
        is_pr = "pull_request" in item
        author = item.get("user", {}).get("login", "") if isinstance(item.get("user"), dict) else ""
        created = _parse_date(item.get("created_at"))

        relevance = _compute_relevance(topic, title, i, reactions_total, comment_count)

        items.append(
            {
                "id": f"GH{i + 1}",
                "title": title,
                "url": html_url,
                "date": created,
                "author": author,
                "repository": repo,
                "snippet": body_text[:300] if body_text else "",
                "relevance": relevance,
                "why_relevant": f"GitHub {'PR' if is_pr else 'issue'}: {title[:60]}",
                "engagement": {
                    "reactions": reactions_total,
                    "comments": comment_count,
                },
                "labels": labels,
                "state": state,
                "is_pr": is_pr,
            }
        )

    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


# ─────────────────────────────────────────────────────────────
# Comment enrichment
# ─────────────────────────────────────────────────────────────


def _fetch_item_comments(
    issue_url: str,
    token: str,
    max_comments: int = 5,
) -> list[dict]:
    """Fetch comments for a GitHub issue/PR."""
    path = issue_url.replace("https://github.com/", "")
    path = path.replace("/pull/", "/issues/")
    api_url = f"{REPO_API}/{path}/comments?per_page={max_comments}&sort=reactions&direction=desc"

    data = _fetch_json(api_url, token=token, timeout=15)
    if not data or not isinstance(data, list):
        return []

    comments = []
    for c in data[:max_comments]:
        body = c.get("body") or ""
        excerpt = body[:300] + "..." if len(body) > 300 else body
        reactions = c.get("reactions", {})
        reaction_count = reactions.get("total_count", 0) if isinstance(reactions, dict) else 0
        author = c.get("user", {}).get("login", "") if isinstance(c.get("user"), dict) else ""
        comments.append(
            {
                "score": reaction_count,
                "excerpt": excerpt,
                "author": author,
            }
        )

    return comments


def enrich_with_comments(
    items: list[dict],
    depth: str = "default",
    token: str | None = None,
) -> list[dict]:
    """Fetch top comments for top-K items by reactions.

    Args:
        items: Parsed GitHub items
        depth: Research depth (controls enrichment count)
        token: Optional GitHub token (falls back to env/gh CLI)

    Returns:
        Items with top_comments added.
    """
    if not items:
        return items

    resolved_token = _resolve_token(token)
    if not resolved_token:
        logger.warning("No GitHub token available for comment enrichment")
        return items

    limit = ENRICH_LIMITS.get(depth, ENRICH_LIMITS["default"])
    by_reactions = sorted(
        range(len(items)),
        key=lambda i: items[i].get("engagement", {}).get("reactions", 0),
        reverse=True,
    )
    to_enrich = by_reactions[:limit]

    logger.info("GitHub enriching top %d items with comments", len(to_enrich))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_item_comments, items[idx]["url"], resolved_token): idx
            for idx in to_enrich
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                comments = future.result(timeout=15)
                items[idx]["top_comments"] = comments
            except Exception as e:
                logger.warning(
                    "GitHub comment enrichment failed for %s: %s", items[idx].get("url"), e
                )

    return items
