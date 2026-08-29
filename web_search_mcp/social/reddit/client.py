"""HTTP client for keyless Reddit search."""

from __future__ import annotations

import contextlib
import json
import socket
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus, urlencode

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._models.types import Depth
from ..._utils import token_overlap_relevance

DEFAULT_TIMEOUT = 30
USER_AGENT = "web-search-mcp/1.0 (Reddit Search)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class HTTPError(Exception):
    """HTTP request error with status code."""

    def __init__(
        self, message: str, status_code: int | None = None, body: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _is_dns_failure(err: urllib.error.URLError) -> bool:
    """Return True if a URLError was caused by DNS resolution (gaierror)."""
    return isinstance(getattr(err, "reason", None), socket.gaierror)


def _should_retry_http(exception: BaseException) -> bool:
    """Retry on rate limits (429) or server errors (5xx)."""
    if isinstance(exception, HTTPError):
        return exception.status_code == 429 or (
            exception.status_code is not None and exception.status_code >= 500
        )
    return isinstance(exception, urllib.error.URLError) and _is_dns_failure(exception)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry_http),
)
def request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    raw: bool = False,
) -> dict[str, Any] | str:
    """Make an HTTP request with exponential backoff for 429/5xx errors."""
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)

    if params:
        filtered = {k: str(v) for k, v in params.items() if v is not None}
        if filtered:
            separator = "&" if ("?" in url) else "?"
            url = f"{url}{separator}{urlencode(filtered)}"

    data = json.dumps(json_data).encode("utf-8") if json_data is not None else None
    if json_data is not None:
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            if raw:
                return body
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = None
        with contextlib.suppress(OSError, UnicodeDecodeError):
            body = e.read().decode("utf-8")

        err = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

        if e.code == 429 or (e.code and e.code >= 500):
            raise err from e
        raise err from e
    except urllib.error.URLError as e:
        if _is_dns_failure(e):
            msg = f"DNS failure: {e.reason}"
            raise HTTPError(msg) from e
        msg = f"URL Error: {e.reason}"
        raise HTTPError(msg) from e
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON response: {e}"
        raise HTTPError(msg) from e
    except (OSError, TimeoutError, ConnectionResetError) as e:
        msg = f"Connection error: {type(e).__name__}: {e}"
        raise HTTPError(msg) from e


def get(url: str, headers: dict[str, str] | None = None, **kwargs) -> dict[str, Any]:
    """Make a GET request."""
    try:
        result = request("GET", url, headers=headers, **kwargs)
        return result if isinstance(result, dict) else {}
    except HTTPError:
        return {}


def get_text(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    accept: str = "*/*",
    headers: dict[str, str] | None = None,
) -> str | None:
    """Fetch a URL and return decoded text, or None on any failure."""
    merged = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        merged.update(headers)
    try:
        result = request("GET", url, headers=merged, timeout=timeout, raw=True)
        return result if isinstance(result, str) else None
    except HTTPError:
        return None


# ── Fallback .json search logic ────────────────────────────────────────────


def _parse_json_posts(data: dict[str, Any], query: str = "") -> list[dict[str, Any]]:
    """Parse Reddit .json response into normalized post dicts."""
    posts: list[dict[str, Any]] = []
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

            created_dt = datetime.fromtimestamp(created_utc, tz=UTC) if created_utc else None
            date_str = created_dt.date().isoformat() if created_dt else None

            relevance = token_overlap_relevance(query, title)

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
                },
            )
    except Exception:
        return []
    return posts


def search_json(topic: str, depth: Depth = "default") -> list[dict[str, Any]]:
    """One-shot global .json search. Returns [] on any failure (403, timeout, etc.)."""
    depth_limits = _ALL_DEPTH_LIMITS["reddit"]
    limit = depth_limits.get(depth, depth_limits["default"])
    q = quote_plus(topic)
    url = f"https://www.reddit.com/search.json?q={q}&limit={limit}&sort=relevance&t=month"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        data = get(url, headers=headers, timeout=15)
        return _parse_json_posts(data, topic)
    except Exception:
        return []
