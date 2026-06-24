"""Shared httpx client instances and JSON API client factory."""

from __future__ import annotations

import logging
import ssl
from urllib.parse import urlparse

import httpx

from .._config import settings

logger = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    """Validate URL has a supported scheme. Returns url unchanged or raises ValueError."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        msg = f"Unsupported URL scheme: {parsed.scheme!r}"
        raise ValueError(msg)
    return url


def _get_ssl_context() -> ssl.SSLContext | None:
    """Get SSL context, with safe fallback for development environments."""
    try:
        return ssl.create_default_context()
    except Exception as e:
        logger.warning("Failed to create default SSL context: %s", e)
        return None


# Global shared client instance
ssl_context = _get_ssl_context()
http_client = httpx.Client(
    timeout=30.0,
    headers={"User-Agent": settings.user_agent},
    follow_redirects=True,
    verify=ssl_context if ssl_context else True,
)


def get_json_client(timeout: float = 15.0) -> httpx.Client:
    """Return a context-managed httpx client configured for JSON API calls."""
    return httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
        },
        verify=ssl_context if ssl_context else True,
    )
