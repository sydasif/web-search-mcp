"""Infrastructure layer for Groq API interaction.
Handles authentication, resilience, and request-size constraints.
"""

import logging
import re
from typing import Any, Literal, Optional
from groq import Groq
from groq._exceptions import APIStatusError
from groq.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from groq.types.chat.completion_create_params import CompletionCreateParams
from groq._types import NotGiven, omit

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)
from .config import settings

logger = logging.getLogger("web-search-mcp")

# Groq's internal web_search tool has a ~4 KB request-body size limit.
_MAX_QUERY_BYTES = 3000


class GroqClientError(Exception):
    """Base exception for Groq client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _retry_if_not_fatal(exception: BaseException) -> bool:
    """
    Determine if a Groq API error should be retried.

    Retry on:
    - 429 Too Many Requests
    - 5xx Server Errors
    - Connection/Timeout issues

    Do NOT retry on:
    - 401 Unauthorized (Invalid API Key)
    - 413 Request Entity Too Large (Query too long)
    - 400 Bad Request
    """
    if isinstance(exception, GroqClientError):
        # Fatal errors: do not retry
        if exception.status_code in (400, 401, 403, 413):
            return False
        # Retryable errors: 429 or 5xx
        if exception.status_code == 429 or (exception.status_code and exception.status_code >= 500):
            return True

    # Retry on generic connection/timeout issues
    msg = str(exception).lower()
    if "timeout" in msg or "connection" in msg or "network" in msg:
        return True

    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_retry_if_not_fatal),
)
def call_groq_api(
    messages: list[ChatCompletionMessageParam],
    model: str,
    temperature: float = 1.0,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    stream: bool = False,
    stop: Optional[list[str]] = None,
    reasoning_effort: Optional[Literal["none", "default", "low", "medium", "high"]] = None,
    tools: Optional[list[ChatCompletionToolParam]] = None,
) -> Any:
    """Unified wrapper for Groq API calls with professional resilience."""
    if not settings.groq_api_key:
        raise GroqClientError("Missing Groq API key", status_code=401)

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            default_headers={"Groq-Model-Version": "latest"},
        )

        response = client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            stop=stop,
            reasoning_effort=reasoning_effort if reasoning_effort is not None else omit,
            tools=tools,
        )
        return response
    except Exception as e:
        msg = str(e)
        if "413" in msg or "request_too_large" in msg or "Request Entity Too Large" in msg:
            raise GroqClientError(f"Request too large: {msg}", status_code=413)

        status_code = None
        if isinstance(e, APIStatusError):
            status_code = e.status_code
        elif hasattr(e, "status_code"):
            status_code = e.status_code
        elif "HTTP" in msg:
            match = re.search(r"HTTP (\d{3})", msg)
            if match:
                status_code = int(match.group(1))

        raise GroqClientError(f"Groq API error: {msg}", status_code=status_code)


def get_client() -> Groq:
    """Return a configured Groq client."""
    return Groq(
        api_key=settings.groq_api_key,
        default_headers={"Groq-Model-Version": "latest"},
    )


def truncate_query(query: str, max_bytes: int = _MAX_QUERY_BYTES) -> str:
    """Truncate a query to stay within Groq's internal request-body size limit."""
    query = " ".join(query.split())
    if len(query.encode("utf-8")) <= max_bytes:
        return query

    lo, hi = 0, len(query)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(query[:mid].encode("utf-8")) <= max_bytes:
            lo = mid
        else:
            hi = mid - 1

    return query[:lo].rstrip()
