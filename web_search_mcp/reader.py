import logging
from typing import Literal

import httpx
import trafilatura
from curl_cffi import CurlError, requests as curl_requests

from .config import settings
from .http_client import http_client
from .models import PageResponse, ErrorResponse
from .utils import RateLimiter, format_error

logger = logging.getLogger("web-search-mcp")

SUPPORTED_FETCH_BACKENDS = ("httpx", "curl", "auto")

_CLOUDFLARE_BODY_SIGNALS = (
    "cf-mitigated",
    "Just a moment...",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
)


def _is_cloudflare_challenge_body(html: str) -> bool:
    """Checks if the HTML body contains signals of a Cloudflare challenge.

    Args:
        html: The HTML content to analyze.

    Returns:
        True if a Cloudflare challenge signal is found, False otherwise.
    """
    if not html:
        return False
    sample = html[:4096].casefold()
    return any(sig.casefold() in sample for sig in _CLOUDFLARE_BODY_SIGNALS)


# Initialize rate limiter for fetching pages
fetch_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_fetch)


def _fetch_httpx(url: str, timeout: int = 30) -> str:
    """Fetches a URL using the httpx client.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds. Defaults to 30.

    Returns:
        The response body as a string.

    Raises:
        httpx.HTTPStatusError: If the response returns a non-2xx status code.
    """
    response = http_client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _fetch_curl(url: str, timeout: int = 30) -> str:
    """Fetches a URL using curl_cffi with Chrome 131 TLS impersonation.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds. Defaults to 30.

    Returns:
        The response body as a string.

    Raises:
        curl_requests.HTTPError: If the response returns a non-2xx status code.
    """
    with curl_requests.Session(impersonate="chrome131") as session:
        response = session.get(url, allow_redirects=True, timeout=timeout)
        response.raise_for_status()
        return response.text


def _fetch_auto(url: str, timeout: int = 30) -> str:
    """Attempts to fetch a URL, falling back to curl if httpx fails or hits Cloudflare.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds. Defaults to 30.

    Returns:
        The response body as a string.

    Raises:
        httpx.HTTPStatusError: If httpx fails with a non-403 status.
    """
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
    """Dispatches the fetch request to the specified backend.

    Args:
        url: The URL to fetch.
        backend: The backend to use ('httpx', 'curl', or 'auto').
        timeout: Request timeout in seconds. Defaults to 30.

    Returns:
        The response body as a string.

    Raises:
        ValueError: If an unsupported backend is specified.
    """
    match backend:
        case "httpx":
            return _fetch_httpx(url, timeout=timeout)
        case "curl":
            return _fetch_curl(url, timeout=timeout)
        case "auto":
            return _fetch_auto(url, timeout=timeout)
        case _:
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
) -> PageResponse | ErrorResponse:
    """Extracts clean text content from a web page URL.

    Args:
        url: The URL to fetch and extract from.
        output_format: The format of the extracted content. Defaults to 'txt'.
        include_metadata: Whether to attempt to extract page metadata. Defaults to False.
        include_tables: Whether to include tables in the extraction. Defaults to False.
        include_comments: Whether to include comments in the extraction. Defaults to False.
        include_images: Whether to include image descriptions. Defaults to False.
        deduplicate: Whether to remove duplicate content. Defaults to True.
        max_length: Maximum length of the returned content string. Defaults to 15000.
        timeout: Request timeout in seconds. Defaults to 30.
        backend: The fetch backend to use ('httpx', 'curl', or 'auto'). Defaults to 'auto'.

    Returns:
        A dictionary containing the URL, content length, and the extracted content.
        May include a 'metadata' field or a 'warning' if metadata extraction failed.
    """
    # Apply rate limiting
    fetch_rate_limiter.acquire()
    try:
        metadata = None
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

        if not extracted_data:
            return format_error("No readable text found.")

        if include_metadata:
            # trafilatura.extract can return a tuple (content, metadata) if with_metadata=True
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

        # Create a PageResponse model for structured data
        response = PageResponse(
            url=url,
            length=actual_length,
            content=str(content)[:max_length],
        )

        if include_metadata:
            if metadata:
                # trafilatura metadata is an object with attributes
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
