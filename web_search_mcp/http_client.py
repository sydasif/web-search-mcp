import logging
import ssl
import httpx
from .config import settings

logger = logging.getLogger("web-search-mcp")


def _get_ssl_context() -> ssl.SSLContext | None:
    """Get SSL context, with safe fallback for development environments."""
    try:
        return ssl.create_default_context()
    except Exception as e:
        logger.warning(f"Failed to create default SSL context: {e}")
        # In production, SSL verification should always be enforced.
        # For development environments with certificate issues, allow fallback.
        return None


def _create_client() -> httpx.Client:
    """Create a shared HTTP client with proper configuration."""
    ssl_context = _get_ssl_context()

    # Determine verify parameter
    # Default is True (verify SSL). If we have a custom context, use it.
    verify: bool | ssl.SSLContext = True
    if ssl_context is not None:
        verify = ssl_context

    return httpx.Client(
        timeout=30.0,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
        verify=verify,
    )


# Global shared client instance
http_client = _create_client()
