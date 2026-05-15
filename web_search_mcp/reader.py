import trafilatura
import logging
import httpx
from typing import Literal
from curl_cffi import requests as curl_requests
from curl_cffi import CurlError

from .http_client import http_client
from .utils import format_error, RateLimiter
from .config import settings

logger = logging.getLogger("web-search-mcp")

SUPPORTED_FETCH_BACKENDS = ("httpx", "curl", "auto")

_CLOUDFLARE_BODY_SIGNALS = (
    "cf-mitigated",
    "Just a moment...",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
)


def _is_cloudflare_challenge_body(html: str) -> bool:
    if not html:
        return False
    sample = html[:4096].casefold()
    return any(sig.casefold() in sample for sig in _CLOUDFLARE_BODY_SIGNALS)


# Initialize rate limiter for fetching pages
fetch_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_fetch)


def _fetch_httpx(url: str, timeout: int = 30) -> str:
    """Fetch URL via httpx. Raises httpx.HTTPStatusError on non-2xx."""
    response = http_client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _fetch_curl(url: str, timeout: int = 30) -> str:
    """Fetch URL via curl_cffi with Chrome 131 TLS impersonation."""
    session: curl_requests.Session = curl_requests.Session(impersonate="chrome131")
    try:
        response = session.get(url, allow_redirects=True, timeout=timeout)
        response.raise_for_status()
        return response.text
    finally:
        session.close()


def _fetch_auto(url: str, timeout: int = 30) -> str:
    """Try httpx first. On 403 or Cloudflare challenge, fall back to curl."""
    try:
        html = _fetch_httpx(url, timeout=timeout)
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 403:
            logger.info(f"httpx got 403 for {url}; retrying with curl backend")
            return _fetch_curl(url, timeout=timeout)
        raise

    if _is_cloudflare_challenge_body(html):
        logger.info(f"httpx got Cloudflare challenge for {url}; retrying with curl backend")
        return _fetch_curl(url, timeout=timeout)

    return html


def _fetch_with_backend(url: str, backend: str, timeout: int = 30) -> str:
    """Fetch URL using the specified backend."""
    if backend == "httpx":
        return _fetch_httpx(url, timeout=timeout)
    elif backend == "curl":
        return _fetch_curl(url, timeout=timeout)
    elif backend == "auto":
        return _fetch_auto(url, timeout=timeout)
    else:
        raise ValueError(
            f"Unknown fetch backend '{backend}'. Supported: {SUPPORTED_FETCH_BACKENDS}"
        )


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
) -> dict:
    """Extracts the full text content from a web page URL."""
    # Apply rate limiting
    fetch_rate_limiter.acquire()
    try:
        html_content = _fetch_with_backend(url, backend=backend, timeout=timeout)

        if not html_content:
            return format_error("Could not download content.")

        # Perform extraction with specified parameters
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

        metadata = None

        if include_metadata:
            if isinstance(extracted_data, tuple):
                content, metadata = extracted_data
            else:
                content = extracted_data
        else:
            content = extracted_data

        if not content:
            return format_error("No readable text found.")

        actual_length = len(str(content))
        response_data = {"url": url, "length": actual_length, "content": str(content)[:max_length]}

        if include_metadata:
            if metadata:
                response_data["metadata"] = {
                    "title": getattr(metadata, "title", None),
                    "author": getattr(metadata, "author", None),
                    "date": getattr(metadata, "date", None),
                    "description": getattr(metadata, "description", None),
                    "fingerprint": getattr(metadata, "fingerprint", None),
                }
            else:
                response_data["warning"] = "Could not extract metadata."

        return response_data

    except httpx.TimeoutException as e:
        logger.error(f"Timeout during fetch: {e}")
        return format_error(f"Request timed out after {timeout}s: {str(e)}")
    except httpx.RequestError as e:
        logger.error(f"HTTP error during fetch: {e}")
        return format_error(f"HTTP request failed: {str(e)}")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else None
        logger.error(f"HTTP status error during fetch: {e}")
        return format_error(f"HTTP request failed with status {status}: {str(e)}")
    except CurlError as e:
        logger.error(f"Curl error during fetch: {e}")
        return format_error(f"HTTP request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Reader error: {e}")
        return format_error(str(e))
