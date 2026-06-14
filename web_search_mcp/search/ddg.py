"""DuckDuckGo search and web retrieval with Exa AI fallback.

Consolidates search and reading functionality with professional resilience.
"""

import logging
from typing import Literal

import httpx
import trafilatura
from ddgs import DDGS
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .._config import settings
from .._http import http_client
from .._models import ErrorResponse, PageResponse, SearchRequest, SearchResponse, SearchResult
from .._utils import RateLimiter, format_error
from .exa import exa_fetch

logger = logging.getLogger(__name__)

# Rate limiters
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)
fetch_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_fetch)


def _should_retry_ddg(exception: BaseException) -> bool:
    """Retry on rate limits (429) or server errors (5xx)."""
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code if exception.response is not None else None
        return status == 429 or (status is not None and status >= 500)
    return bool(isinstance(exception, (httpx.TimeoutException, httpx.RequestError)))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry_ddg),
)
def _fetch_httpx(url: str, timeout: int) -> str:
    """Fetches a URL using the shared httpx client."""
    response = http_client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _request_with_fallback(url: str, timeout: int = 30) -> tuple[str, bool]:
    """Fetch a URL. Tries httpx (with retries), falls back to Exa server-side render.

    Returns (content, used_exa_fallback). When used_exa_fallback is True, content is markdown.
    """
    try:
        return _fetch_httpx(url, timeout=timeout), False
    except (httpx.HTTPStatusError, httpx.RequestError, RetryError) as e:
        cause = e.last_attempt.exception() if isinstance(e, RetryError) and e.last_attempt else e
        logger.warning("httpx failed for %s (%s); using Exa fallback", url, cause)
        try:
            content = exa_fetch([url], timeout=timeout)
        except Exception as exa_err:
            logger.warning("Exa fallback also failed for %s: %s", url, exa_err)
            raise
        if content:
            return content, True
        raise


def _fetch_pdf_text(url: str, timeout: int = 30, max_length: int = 15000) -> str | None:
    """Download a PDF and extract its text content using pypdf."""
    import io

    import pypdf

    try:
        response = http_client.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)

        text_parts: list[str] = []
        total = 0
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
                total += len(page_text)
                if total >= max_length:
                    break

        if not text_parts:
            return None

        result = "\n\n".join(text_parts)
        return result[:max_length]
    except Exception:
        logger.exception("PDF extraction failed for %s", url)
        return None


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
        exclude={"query", "search_type", "response_format"},
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
                next_page=request.page + 1 if has_more else None,
            )
    except Exception as e:
        logger.exception("DuckDuckGo search failed for query %r", request.query)
        return format_error(str(e))


def fetch_page(
    url: str,
    output_format: Literal[
        "csv",
        "html",
        "json",
        "markdown",
        "python",
        "txt",
        "xml",
        "xmltei",
    ] = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> PageResponse | ErrorResponse:
    """Extracts clean text content from a web page or PDF URL."""
    fetch_rate_limiter.acquire()

    # PDF URLs: extract text directly from the binary PDF
    if url.lower().endswith(".pdf") or "/pdf/" in url.lower() or "pdf=" in url.lower():
        pdf_text = _fetch_pdf_text(url, timeout=timeout, max_length=max_length)
        if pdf_text:
            return PageResponse(url=url, length=len(pdf_text), content=pdf_text)
        # Fall through to normal HTML extraction if PDF fails

    try:
        raw_content, used_exa = _request_with_fallback(url, timeout=timeout)

        if not raw_content:
            return format_error("Could not download content.")

        # Exa returns clean markdown — trafilatura would degrade it
        if used_exa:
            actual_length = len(raw_content)
            return PageResponse(
                url=url,
                length=actual_length,
                content=raw_content[:max_length],
            )

        extracted_data = trafilatura.extract(
            raw_content,
            output_format=output_format,
            with_metadata=include_metadata,
            include_tables=include_tables,
            include_comments=include_comments,
            include_links=True,
            include_images=include_images,
            deduplicate=deduplicate,
        )

        if not extracted_data:
            return format_error("No readable text found.")

        if include_metadata:
            if isinstance(extracted_data, tuple):
                content, metadata = extracted_data
            else:
                content = extracted_data
                metadata = None
        else:
            content = extracted_data
            metadata = None

        if not content:
            return format_error("No readable text found.")

        actual_length = len(str(content))

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
    except (httpx.HTTPStatusError, httpx.RequestError, RetryError) as e:
        cause = e.last_attempt.exception() if isinstance(e, RetryError) and e.last_attempt else e
        logger.exception("Fetch error")
        return format_error(f"HTTP request failed: {cause!s}")
    except Exception as e:
        logger.exception("Reader error")
        return format_error(str(e))
