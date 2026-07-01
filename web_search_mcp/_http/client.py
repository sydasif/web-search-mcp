"""Shared httpx client instances and JSON API client factory."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

import httpx

from .._config import settings

logger = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    """Validate URL has a supported scheme and is not a private/internal address.

    Blocks:
    - Unsupported schemes (non-http/https)
    - All non-public IP ranges: loopback (127/8, ::1), private (10/8, 172.16/12,
      192.168/16, fd00::/8), link-local (169.254/16, fe80::/10), carrier-grade
      NAT (100.64.0.0/10), and reserved (240.0.0.0/4, ::2)
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        msg = f"Unsupported URL scheme: {parsed.scheme!r}"
        raise ValueError(msg)

    host = (parsed.hostname or "").strip()
    if not host:
        msg = "URL has no hostname"
        raise ValueError(msg)

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Domain names are resolved by the server/OS, not here.
        return url

    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    blocked = addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    if blocked:
        msg = f"URL resolves to a blocked address range: {addr}"
        raise ValueError(msg)

    return url


http_client = httpx.Client(
    timeout=30.0,
    headers={"User-Agent": settings.user_agent},
    follow_redirects=True,
    verify=True,
)


def get_json_client(timeout: float = 15.0) -> httpx.Client:
    """Return a context-managed httpx client configured for JSON API calls."""
    return httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
        },
        verify=True,
    )
