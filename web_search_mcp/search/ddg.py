"""DuckDuckGo search and web retrieval with Exa AI fallback.

Consolidates search and reading functionality with professional resilience.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import trafilatura
from ddgs import DDGS

from .._config import settings
from .._http import http_client, validate_url
from .._models import (
    ErrorResponse,
    FetchOutputFormat,
    PageResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from .._utils import RateLimiter, format_error
from .exa import exa_fetch

logger = logging.getLogger(__name__)

# Rate limiters
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)
fetch_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_fetch)


def _fetch_httpx(url: str, timeout: int) -> str:
    """Fetches a URL using the shared httpx client."""
    response = http_client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _request_with_fallback(url: str, timeout: int = 30, max_chars: int = 15000) -> tuple[str, bool]:
    """Fetch a URL. Tries httpx once, falls back to Exa server-side render.

    Returns (content, used_exa_fallback). When used_exa_fallback is True, content is markdown.
    """
    validate_url(url)
    try:
        return _fetch_httpx(url, timeout=timeout), False
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.warning("httpx failed for %s (%s); using Exa fallback", url, e)
        try:
            content = exa_fetch([url], max_chars=max_chars)
        except Exception as exa_err:
            logger.warning("Exa fallback also failed for %s: %s", url, exa_err)
            raise
        if content:
            return content, True
        raise


def format_search_results_markdown(results: SearchResponse | ErrorResponse) -> str:
    """Formats search results as a human-readable markdown string."""
    if isinstance(results, ErrorResponse):
        return f"**Error:** {results.error}"

    lines = [
        f"# Search Results for '{results.query}' ({results.search_type})",
        f"Found {results.total_results} results.",
        "",
    ]

    if not results.results:
        lines.append("No results found.")
        return "\n".join(lines)

    for i, res in enumerate(results.results, 1):
        url = res.href or res.url or "#"
        lines.append(f"{i}. **[{res.title}]({url})**")
        if res.body:
            lines.append(f"   {res.body}")
        lines.append("")

    if results.has_more and results.next_page:
        lines.append(f"\n*More results available. See page {results.next_page}.*")

    return "\n".join(lines)


def ddg_search(request: SearchRequest) -> SearchResponse | ErrorResponse:
    """Performs a web or news search using DuckDuckGo."""
    if not request.query:
        return format_error("Query cannot be empty")

    search_rate_limiter.acquire()

    kwargs = request.model_dump(
        exclude={"query", "search_type", "response_format", "provider"},
        exclude_none=True,
    )
    if "time_range" in kwargs:
        kwargs["timelimit"] = kwargs.pop("time_range")

    try:
        with DDGS() as ddgs:
            search_methods = {"text": ddgs.text, "news": ddgs.news}
            if request.search_type not in search_methods:
                return format_error(f"Unsupported search type: {request.search_type}")

            search_func = search_methods[request.search_type]
            raw_results = list(search_func(request.query, **kwargs))

            has_more = len(raw_results) >= request.max_results

            return SearchResponse(
                query=request.query,
                search_type=request.search_type,
                total_results=len(raw_results),
                results=[SearchResult(**res) for res in raw_results],
                has_more=has_more,
                next_page=None,
            )
    except Exception as e:
        logger.exception("DuckDuckGo search failed for query %r", request.query)
        return format_error(str(e))


def fetch_page(
    url: str,
    output_format: FetchOutputFormat = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> PageResponse | ErrorResponse:
    """Extract clean text content from a web page URL.

    Timeout applies to the httpx extraction path only. The Exa fallback
    uses the SDK's own client-level timeout.
    """
    fetch_rate_limiter.acquire()

    try:
        raw_content, used_exa = _request_with_fallback(url, timeout=timeout, max_chars=max_length)

        if not raw_content:
            return format_error("Could not download content.")

        # Exa returns clean markdown — trafilatura would degrade it
        if used_exa:
            return _handle_exa_response(url, raw_content, max_length)

        return _handle_trafilatura_response(
            url,
            raw_content,
            output_format,
            include_metadata,
            include_tables,
            deduplicate,
            max_length,
        )
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.exception("Fetch error")
        return format_error(f"HTTP request failed: {e}")
    except Exception as e:
        logger.exception("Reader error")
        return format_error(str(e))


def _handle_exa_response(url: str, content: str, max_length: int) -> PageResponse:
    """Handle response when Exa was used for fetching."""
    actual_length = len(content)
    return PageResponse(
        url=url,
        length=actual_length,
        content=content[:max_length],
    )


def _handle_trafilatura_response(
    url: str,
    raw_content: str,
    output_format: FetchOutputFormat,
    include_metadata: bool,
    include_tables: bool,
    deduplicate: bool,
    max_length: int,
) -> PageResponse | ErrorResponse:
    """Handle response using trafilatura extraction."""
    extracted_data = trafilatura.extract(
        raw_content,
        output_format=output_format,
        with_metadata=include_metadata,
        include_tables=include_tables,
        include_links=True,
        deduplicate=deduplicate,
    )

    # trafilatura failed — try Exa server-side render as second fallback
    if not extracted_data:
        logger.info("trafilatura returned no text for %s; trying Exa fallback", url)
        try:
            exa_content = exa_fetch([url], max_chars=max_length)
        except Exception as exa_err:
            logger.warning("Exa fallback failed for %s: %s", url, exa_err)
            exa_content = None
        if exa_content:
            actual_length = len(exa_content)
            return PageResponse(
                url=url,
                length=actual_length,
                content=exa_content[:max_length],
            )
        return format_error("No readable text found.")

    return _process_trafilatura_result(url, extracted_data, include_metadata, max_length)


def _process_trafilatura_result(
    url: str,
    extracted_data: str | tuple[str, Any],
    include_metadata: bool,
    max_length: int,
) -> PageResponse | ErrorResponse:
    """Process trafilatura extraction result into PageResponse."""
    content: str | tuple[str, Any] = extracted_data
    metadata: Any = None

    if include_metadata:
        if isinstance(extracted_data, tuple):
            content, metadata = extracted_data
        else:
            content = extracted_data
    else:
        content = extracted_data

    if not content:
        return format_error("No readable text found.")

    actual_length = len(content)

    response = PageResponse(
        url=url,
        length=actual_length,
        content=str(content)[:max_length],
    )

    if include_metadata:
        if metadata:
            meta_dict = {
                "title": getattr(metadata, "title", None),
                "author": getattr(metadata, "author", None),
                "date": getattr(metadata, "date", None),
                "description": getattr(metadata, "description", None),
                "fingerprint": getattr(metadata, "fingerprint", None),
            }
            response.metadata = meta_dict
        else:
            response.warning = "Could not extract metadata."

    return response
