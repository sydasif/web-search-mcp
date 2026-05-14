import logging

logger = logging.getLogger("web-search-mcp")


def format_error(message: str, details: str | None = None) -> dict:
    """Unified error response format."""
    return {
        "error": message,
        "details": details or "No additional details provided.",
    }
