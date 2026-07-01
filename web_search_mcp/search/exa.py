"""Exa AI search and content fetch via the exa_py SDK.

EXA_API_KEY is required for the SDK to function.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from .._config import settings
from .._models import ErrorResponse, SearchResponse, SearchResult
from .._models.types import SearchType
from .._utils import RateLimiter, format_error

if TYPE_CHECKING:
    from exa_py import Exa

logger = logging.getLogger(__name__)

# Rate limit: 10 requests/minute (conservative for free tier 20K/month)
_exa_rate_limiter = RateLimiter(requests_per_minute=10)

# Lazy SDK client
_exa_client: Exa | None = None


def _get_client() -> Exa:
    """Lazy-init the Exa SDK client. Raises RuntimeError if unavailable."""
    global _exa_client
    if _exa_client is None:
        try:
            from exa_py import Exa

            _exa_client = Exa(api_key=settings.exa_api_key)
        except ImportError:
            raise RuntimeError("exa_py SDK is not installed. Run: uv add exa-py") from None
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Exa SDK: {e}") from e
    return _exa_client


# ── Helpers ────────────────────────────────────────────────────────────────


def _time_range_to_dates(time_range: str | None) -> tuple[str | None, str | None]:
    """Convert DDG-style time_range ('d', 'w', 'm', 'y') to ISO date strings.

    Returns (start_published_date, end_published_date).
    """
    if time_range is None:
        return None, None

    now = datetime.now(UTC)
    mapping = {
        "d": timedelta(days=1),
        "w": timedelta(days=7),
        "m": timedelta(days=30),
        "y": timedelta(days=365),
    }
    delta = mapping.get(time_range)
    if delta is None:
        return None, None

    start = (now - delta).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return start, None


def _region_to_user_location(region: str | None) -> str | None:
    """Convert DDG-style region ('us-en', 'uk-en') to two-letter ISO country code."""
    if region is None:
        return None
    parts = region.split("-")
    code = parts[0].lower() if parts else ""
    # Handle non-ISO exceptions (e.g. 'uk' → 'GB')
    exceptions = {"uk": "gb"}
    code = exceptions.get(code, code)
    return code.upper() if code else None


# ── Search ─────────────────────────────────────────────────────────────────


def exa_search(
    query: str,
    max_results: int = 5,
    search_type: SearchType = "text",
    time_range: str | None = None,
    domain: str | None = None,
    region: str | None = None,
) -> SearchResponse | ErrorResponse:
    """Search via Exa AI.

    Args:
        query: Search query string.
        max_results: Max number of results (default 5).
        search_type: 'text' or 'news'. News maps to Exa category='news'.
        time_range: Time filter 'd'/'w'/'m'/'y' → start_published_date.
        domain: Domain to scope results to → include_domains.
        region: Geographic region (e.g. 'us-en') → user_location.

    Returns:
        SearchResponse: Structured search results.
        ErrorResponse: Error response if the search fails.
    """
    if not query:
        return format_error("Query cannot be empty")

    try:
        client = _get_client()
    except RuntimeError as e:
        return format_error(str(e))

    _exa_rate_limiter.acquire()

    # Build kwargs from the unified params
    kwargs: dict = {
        "query": query,
        "num_results": max_results,
        "contents": False,  # metadata only, no page text
    }

    if domain:
        kwargs["include_domains"] = [domain]

    start_date, end_date = _time_range_to_dates(time_range)
    if start_date:
        kwargs["start_published_date"] = start_date
    if end_date:
        kwargs["end_published_date"] = end_date

    if search_type == "news":
        kwargs["category"] = "news"

    user_loc = _region_to_user_location(region)
    if user_loc:
        kwargs["user_location"] = user_loc

    try:
        response = client.search(**kwargs)
    except Exception as e:
        logger.exception("Exa SDK search failed for query %r", query)
        return format_error(f"Exa search failed: {e}")

    # Convert SDK response to SearchResponse
    results_list: list[SearchResult] = []
    for r in getattr(response, "results", []) or []:
        url = getattr(r, "url", "") or ""
        results_list.append(
            SearchResult(
                title=getattr(r, "title", None),
                href=url,
                url=url,
                body=None,
            )
        )

    return SearchResponse(
        query=query,
        search_type=search_type,
        total_results=len(results_list),
        results=results_list,
        has_more=False,
    )


# ── Fetch ──────────────────────────────────────────────────────────────────


def exa_fetch(urls: list[str], max_chars: int = 15000) -> str | None:
    """Fetch page content via Exa. Returns markdown text or None.

    Handles JS-heavy pages, Cloudflare challenges, and paywalls that
    httpx cannot access.
    """
    if not urls:
        return None

    try:
        client = _get_client()
    except RuntimeError:
        logger.warning("Exa SDK not available; cannot fetch")
        return None

    _exa_rate_limiter.acquire()
    try:
        response = client.get_contents(urls)
    except Exception as e:
        logger.warning("Exa SDK get_contents failed for %s: %s", urls, e)
        return None

    parts: list[str] = []
    for r in getattr(response, "results", []) or []:
        url = getattr(r, "url", "")
        title = getattr(r, "title", "")
        text = getattr(r, "text", "")
        if text:
            parts.append(f"# {title}\n\nSource: {url}\n\n{text}")
        elif title:
            parts.append(f"# {title}\n\nSource: {url}")

    if not parts:
        return None

    result = "\n\n---\n\n".join(parts)
    return result[:max_chars]
