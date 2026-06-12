"""DuckDuckGo search and web retrieval logic.
Consolidates search and reading functionality with professional resilience.
"""

import logging
from typing import Literal

import httpx
import trafilatura
from curl_cffi import CurlError, requests as curl_requests
from ddgs import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .config import settings
from .http_client import http_client
from .models import SearchRequest, SearchResponse, SearchResult, PageResponse, ErrorResponse
from .utils import RateLimiter, format_error

logger = logging.getLogger(__name__)

# Rate limiters
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)
fetch_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_fetch)

# Cloudflare detection signals
_CLOUDFLARE_BODY_SIGNALS = (
    "cf-mitigated",
    "Just a moment...",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
)


def _is_cloudflare_challenge_body(html: str) -> bool:
    """Checks if the HTML body contains signals of a Cloudflare challenge."""
    if not html:
        return False
    sample = html[:4096].casefold()
    return any(sig.casefold() in sample for sig in _CLOUDFLARE_BODY_SIGNALS)


def _should_retry_ddg(exception: BaseException) -> bool:
    """Retry on rate limits (429) or server errors (5xx)."""
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code if exception.response is not None else None
        return status == 429 or (status is not None and status >= 500)
    if isinstance(exception, (httpx.TimeoutException, httpx.RequestError)):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry_ddg),
)
def _request_with_fallback(url: str, timeout: int = 30, backend: str = "auto") -> str:
    """Fetches a URL, falling back to curl_cffi if httpx fails or hits Cloudflare."""
    VALID_BACKENDS = {"auto", "curl", "httpx"}
    if backend not in VALID_BACKENDS:
        raise ValueError(
            f"Unknown fetch backend {backend!r}. Supported: {', '.join(sorted(VALID_BACKENDS))}"
        )
    if backend == "curl":
        return _fetch_curl(url, timeout)
    if backend == "httpx":
        return _fetch_httpx(url, timeout)

    # 'auto' backend: try httpx, then curl if needed
    try:
        html = _fetch_httpx(url, timeout=timeout)
        if _is_cloudflare_challenge_body(html):
            logger.info("httpx got Cloudflare challenge for %s; retrying with curl backend", url)
            return _fetch_curl(url, timeout=timeout)
        return html
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 403:
            logger.info("httpx got 403 for %s; retrying with curl backend", url)
            return _fetch_curl(url, timeout=timeout)
        raise


def _fetch_httpx(url: str, timeout: int) -> str:
    """Fetches a URL using the shared httpx client."""
    response = http_client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _fetch_curl(url: str, timeout: int) -> str:
    """Fetches a URL using curl_cffi with Chrome 131 TLS impersonation."""
    with curl_requests.Session(impersonate="chrome131") as session:
        response = session.get(url, allow_redirects=True, timeout=timeout)
        response.raise_for_status()
        return response.text


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
    except Exception as e:
        logger.error("PDF extraction failed for %s: %s", url, e)
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
        exclude={"query", "search_type", "response_format"}, exclude_none=True
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
        "csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"
    ] = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
    backend: Literal["httpx", "curl", "auto"] = "auto",
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
        html_content = _request_with_fallback(url, timeout=timeout, backend=backend)

        if not html_content:
            return format_error("Could not download content.")

        extracted_data = trafilatura.extract(
            html_content,
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
    except (httpx.HTTPStatusError, httpx.RequestError, CurlError) as e:
        logger.error("Fetch error: %s", e)
        return format_error(f"HTTP request failed: {str(e)}")
    except Exception as e:
        logger.error("Reader error: %s", e)
        return format_error(str(e))
