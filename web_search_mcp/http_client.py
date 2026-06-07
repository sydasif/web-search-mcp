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
