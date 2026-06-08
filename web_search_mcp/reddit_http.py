"""HTTP utilities for keyless Reddit search (stdlib only)."""

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
MAX_429_RETRIES = 2
RETRY_DELAY = 2.0
MIN_DNS_RETRIES = 3
USER_AGENT = "web-search-mcp/1.0 (Reddit Search)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _is_dns_failure(err: urllib.error.URLError) -> bool:
    """Return True if a URLError was caused by DNS resolution (gaierror)."""
    return isinstance(getattr(err, "reason", None), socket.gaierror)


class HTTPError(Exception):
    """HTTP request error with status code."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    max_429_retries: int = MAX_429_RETRIES,
    raw: bool = False,
) -> Union[Dict[str, Any], str]:
    """Make an HTTP request and return JSON response."""
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)

    if params:
        filtered = {k: str(v) for k, v in params.items() if v is not None}
        if filtered:
            separator = "&" if ("?" in url) else "?"
            url = f"{url}{separator}{urlencode(filtered)}"

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    last_error = None
    rate_limit_count = 0
    effective_retries = retries
    dns_attempts = 0
    attempt = 0
    while attempt < effective_retries:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                if raw:
                    return body
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = None
            try:
                body = e.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                pass
            last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

            # Don't retry client errors (4xx) except rate limits
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error

            # Cap 429 retries separately
            if e.code == 429:
                rate_limit_count += 1
                if rate_limit_count >= max_429_retries:
                    raise last_error

            if attempt < retries - 1:
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = RETRY_DELAY * (2**attempt) + 1
                    else:
                        delay = RETRY_DELAY * (2**attempt) + 1
                else:
                    delay = RETRY_DELAY * (2**attempt)
                time.sleep(delay)
            else:
                break
        except urllib.error.URLError as e:
            last_error = HTTPError(f"URL Error: {e.reason}")
            if _is_dns_failure(e):
                dns_attempts += 1
                if effective_retries < MIN_DNS_RETRIES:
                    effective_retries = MIN_DNS_RETRIES
                if attempt < effective_retries - 1:
                    delay = 2 ** (dns_attempts - 1)
                    time.sleep(delay)
            elif attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                break
        except json.JSONDecodeError as e:
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                break

        attempt += 1

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request."""
    result = request("GET", url, headers=headers, **kwargs)
    return result if isinstance(result, dict) else {}


def get_text(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
    accept: str = "*/*",
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Fetch a URL and return decoded text, or None on any failure.

    Keyless helper for Reddit RSS and shreddit HTML endpoints — the free path
    that replaced the now-403 .json endpoints. Sends a browser User-Agent
    and never raises: returns None on HTTP error, network failure, or timeout
    so tiered callers can fall through to the next source.
    """
    merged = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        merged.update(headers)
    try:
        result = request("GET", url, headers=merged, timeout=timeout, retries=retries, raw=True)
        return result if isinstance(result, str) else None
    except HTTPError:
        return None
