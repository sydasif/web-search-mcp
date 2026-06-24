"""GitHub Issues/PRs search via the public GitHub Search API.

Uses api.github.com/search/issues for issue/PR discovery and
per-item comment enrichment. Auth via GITHUB_TOKEN env var or
`gh auth token` subprocess fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, urlparse

import httpx

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._config import ENRICH_LIMITS as _ALL_ENRICH_LIMITS
from .._config import settings
from .._utils import compute_relevance, format_results_markdown, iso_to_date, truncate_content

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.github.com/search/issues"
REPO_API = "https://api.github.com/repos"

DEPTH_LIMITS = _ALL_DEPTH_LIMITS["github"]
ENRICH_LIMITS = _ALL_ENRICH_LIMITS["github"]

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
        "User-Agent": settings.user_agent,
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

    if not topic or not topic.strip():
        logger.warning("GitHub search called with empty topic")
        return []

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
        created = iso_to_date(item.get("created_at"))

        relevance = compute_relevance(topic, title, i, reactions_total + comment_count)

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
            },
        )

    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


def format_github_markdown(items: list[dict], query: str) -> str:
    """Format GitHub results as markdown."""

    def _item_lines(item: dict, i: int) -> list[str]:
        emoji = "\U0001f500" if item.get("is_pr") else "\U0001f41b"
        repo = item.get("repository", "")
        reactions = item.get("engagement", {}).get("reactions", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        lines = [
            f"{i}. {emoji} **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**",
            f"   {repo} | {item.get('author', '')} | {item.get('date', '')}",
            f"   \u2764\ufe0f {reactions} reactions, \U0001f4ac {comments} comments",
        ]
        labels = item.get("labels", [])
        if labels:
            lines.append(f"   Labels: {', '.join(labels[:5])}")
        if item.get("top_comments"):
            lines.append("   Top comment:")
            for c in item["top_comments"][:1]:
                lines.append(f"   > {c.get('excerpt', '')[:200]}...")
        return lines

    return format_results_markdown(items, query, "GitHub", "issues/PRs", _item_lines)


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
            },
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
                    "GitHub comment enrichment failed for %s: %s",
                    items[idx].get("url"),
                    e,
                )

    return items


# ─────────────────────────────────────────────────────────────
# Issue/PR thread rendering via gh CLI
# ─────────────────────────────────────────────────────────────


_GITHUB_ISSUE_RE = re.compile(r"^/([^/]+)/([^/]+)/issues/(\d+)(?:/|$)")
_GITHUB_PR_RE = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)(?:/|$)")


def parse_github_url(url: str) -> tuple[str, str, int, str]:
    """Parse a GitHub issue or PR URL.

    Returns (owner, repo, number, type) where type is 'issue' or 'pr'.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"github.com", "www.github.com"}:
        msg = f"Unsupported GitHub host: {host or '(missing)'}"
        raise ValueError(msg)
    path = parsed.path or ""

    m = _GITHUB_ISSUE_RE.match(path)
    if m:
        return (m.group(1), m.group(2), int(m.group(3)), "issue")

    m = _GITHUB_PR_RE.match(path)
    if m:
        return (m.group(1), m.group(2), int(m.group(3)), "pr")

    raise ValueError(
        "URL is not a recognized GitHub Issue or PR URL. "
        "Expected format: https://github.com/owner/repo/issues/{number} "
        "or https://github.com/owner/repo/pull/{number}",
    )


_REACTION_EMOJI: dict[str, str] = {
    "THUMBS_UP": "\U0001f44d",
    "THUMBS_DOWN": "\U0001f44e",
    "LAUGH": "\U0001f604",
    "HOORAY": "\U0001f389",
    "CONFUSED": "\U0001f615",
    "HEART": "\u2764\ufe0f",
    "ROCKET": "\U0001f680",
    "EYES": "\U0001f440",
}


def _sum_reactions(reaction_groups: list[dict] | None) -> dict[str, int]:
    """Sum reaction counts from reactionGroups array."""
    counts: dict[str, int] = {}
    if not reaction_groups:
        return counts
    for rg in reaction_groups:
        if not isinstance(rg, dict):
            continue
        content = rg.get("content")
        users = rg.get("users")
        if isinstance(content, str) and isinstance(users, dict):
            try:
                count = int(users.get("totalCount") or 0)
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                counts[content] = count
    return counts


def _render_reactions_bar(counts: dict[str, int]) -> str:
    """Render reaction counts as an inline list of emoji+N."""
    if not counts:
        return ""
    parts: list[str] = []
    for content in (
        "THUMBS_UP",
        "HEART",
        "HOORAY",
        "ROCKET",
        "EYES",
        "LAUGH",
        "THUMBS_DOWN",
        "CONFUSED",
    ):
        n = counts.get(content, 0)
        if n > 0:
            emoji = _REACTION_EMOJI.get(content, content.lower())
            parts.append(f"{emoji} {n}")
    return " | ".join(parts)


def render_issue_markdown(data: dict, kind: str = "issue") -> str:
    """Render a gh issue view --json response as structured Markdown."""

    lines: list[str] = []

    # ── header ──
    title = data.get("title") or "Untitled"
    url = data.get("url") or ""
    author = ""
    author_data = data.get("author")
    if isinstance(author_data, dict):
        author = str(author_data.get("login") or "")
    created = iso_to_date(data.get("createdAt")) or ""
    state = (data.get("state") or "").lower()
    match state:
        case "merged":
            state_emoji = "\U0001f300"
        case "closed":
            state_emoji = "\u2705"
        case _:
            state_emoji = "\U0001f6a7"

    heading = "# Pull Request" if kind == "pr" else "# Issue"
    lines.append(heading)
    lines.append(
        f"Title: {title} Link: {url} Author: @{author} Date: {created} State: {state_emoji} {state}",
    )
    lines.append("")

    # ── reactions on the issue ──
    issue_rx = _sum_reactions(data.get("reactionGroups"))
    rx_bar = _render_reactions_bar(issue_rx)
    if rx_bar:
        lines.append(rx_bar)
        lines.append("")

    # ── body ──
    body = (data.get("body") or "").strip()
    if body:
        lines.append(body)
        lines.append("")

    # ── comments ──
    raw_comments = data.get("comments")
    if not isinstance(raw_comments, list) or not raw_comments:
        lines.append("# Comments")
        lines.append("_No comments._")
        lines.append("")
    else:
        # Filter out minimized, sort by total reactions desc
        active = [c for c in raw_comments if isinstance(c, dict) and not c.get("isMinimized")]

        def _total_rx(c: dict) -> int:
            return sum(_sum_reactions(c.get("reactionGroups")).values())

        active.sort(key=_total_rx, reverse=True)

        lines.append("# Comments")
        lines.append("")
        for idx, c in enumerate(active, start=1):
            c_author = ""
            ca = c.get("author")
            if isinstance(ca, dict):
                c_author = str(ca.get("login") or "")
            c_assoc = (c.get("authorAssociation") or "").upper()
            c_date = iso_to_date(c.get("createdAt")) or ""
            c_url = c.get("url") or ""
            c_body = (c.get("body") or "").strip()
            c_rx = _sum_reactions(c.get("reactionGroups"))

            header = f"## Comment {idx}"
            if c_assoc == "MEMBER":
                header += " \U0001f3f7\ufe0f"
            elif c_assoc == "COLLABORATOR":
                header += " \U0001f91d"
            elif c_assoc == "OWNER":
                header += " \U0001f451"
            lines.append(header)

            meta = []
            if c_author:
                meta.append(f"Author: @{c_author}")
            if c_date:
                meta.append(f"Date: {c_date}")
            rx_bar_c = _render_reactions_bar(c_rx)
            if rx_bar_c:
                meta.append(f"Reactions: {rx_bar_c}")
            if c_url:
                meta.append(f"[permalink]({c_url})")
            lines.append(" | ".join(meta))
            lines.append("")

            if c_body:
                lines.append(c_body)
            else:
                lines.append("_No text._")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def _gh_available() -> bool:
    """Check if gh CLI is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _gh_authenticated() -> bool:
    """Check if gh CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def get_github_issue(url: str) -> str:
    """Fetch a GitHub Issue or PR with all comments as structured Markdown."""

    try:
        owner, repo, number, kind = parse_github_url(url)
    except ValueError as e:
        return f"_Error: {e}_\n"

    if not _gh_available():
        return (
            "_Error: `gh` CLI is not installed._\n\n"
            "Install it from https://cli.github.com/ or use `github_search` "
            "with `GITHUB_TOKEN` environment variable instead.\n"
        )

    if not _gh_authenticated():
        return (
            "_Error: `gh` CLI is not authenticated._\n\n"
            "Run `gh auth login` or set `GITHUB_TOKEN` environment variable.\n"
        )

    cmd = [
        "gh",
        "issue" if kind == "issue" else "pr",
        "view",
        str(number),
        "--repo",
        f"{owner}/{repo}",
        "--comments",
        "--json",
        "title,body,url,state,createdAt,author,reactionGroups,comments",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return "_Error: `gh` CLI not found even though it was available earlier.\n"
    except subprocess.TimeoutExpired:
        return f"_Error: Request timed out for {url}_\n"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            return f"_Error: `gh` failed: {stderr}_\n"
        return f"_Error: `gh` returned exit code {result.returncode}_\n"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return f"_Error: Failed to parse `gh` output: {e}_\n"

    if not isinstance(data, dict):
        return "_Error: `gh` returned unexpected data format._\n"

    md = render_issue_markdown(data, kind=kind)

    return truncate_content(md, "GITHUB_ISSUE_MAX_CHARS")
