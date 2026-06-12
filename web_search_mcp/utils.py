import logging
import re
import time
import threading
from .models import ErrorResponse

logger = logging.getLogger(__name__)


def token_overlap_relevance(query: str, text: str) -> float:
    """Simple token overlap relevance score (0.0 to 1.0)."""
    if not query or not text:
        return 0.0
    q_tokens = set(re.findall(r"\w+", query.lower()))
    t_tokens = set(re.findall(r"\w+", text.lower()))
    if not q_tokens or not t_tokens:
        return 0.0
    intersection = q_tokens & t_tokens
    return len(intersection) / len(q_tokens)


def format_error(message: str, details: str | None = None) -> ErrorResponse:
    """Creates a unified error response.

    Args:
        message: A concise summary of the error with suggested next step.
        details: Additional details or exception messages. Defaults to None.

    Returns:
        An ErrorResponse containing the error message and details.
    """
    return ErrorResponse(
        error=message,
        details=details or "No additional details provided.",
    )


def format_auth_error() -> ErrorResponse:
    """Returns a consistent authentication error."""
    return ErrorResponse(
        error="Groq API key not configured",
        details="Set SEARCH_MCP_GROQ_API_KEY in your MCP config or environment.",
    )


def format_empty_query_error() -> ErrorResponse:
    """Returns a consistent empty-query error."""
    return ErrorResponse(
        error="Query cannot be empty",
        details="Provide a non-empty query string. Example: 'latest AI research papers June 2026'",
    )


def format_empty_response_error(source: str = "Groq") -> ErrorResponse:
    """Returns a consistent empty-content error."""
    return ErrorResponse(
        error=f"{source} returned empty content",
        details="The model produced no response. Try rephrasing your query with more specific detail, or switch to a different tool (e.g. web_search for DDG results, groq_search for AI-powered research).",
    )


class RateLimiter:
    """A simple sliding window rate limiter.

    Args:
        requests_per_minute: Maximum number of requests allowed per minute.
        window_seconds: The time window in seconds to track requests. Defaults to 60.0.
    """

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0):
        if requests_per_minute < 0:
            raise ValueError("requests_per_minute must be >= 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until a request can be made without exceeding the rate limit.

        This method implements a sliding window algorithm, removing requests older
        than the window_seconds and sleeping if the limit is reached.
        """
        if self.requests_per_minute <= 0:
            return

        while True:
            with self._lock:
                now = time.time()
                # Remove requests older than the window
                self.requests = [req for req in self.requests if now - req < self.window_seconds]

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                # Calculate wait time based on the oldest request in the window
                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                time.sleep(wait_time)
