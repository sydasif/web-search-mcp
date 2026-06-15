"""Infrastructure layer for Groq API interaction.
Handles authentication, resilience, and request-size constraints.
"""

import logging
import re
from typing import Any, Literal

from groq import Groq
from groq._exceptions import APIStatusError
from groq._types import omit
from groq.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .._config import settings

logger = logging.getLogger(__name__)

# Groq's internal web_search tool has a ~4 KB request-body size limit.
_MAX_QUERY_BYTES = 3000


class GroqClientError(Exception):
    """Base exception for Groq client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _retry_if_not_fatal(exception: BaseException) -> bool:
    """Determine if a Groq API error should be retried."""
    if isinstance(exception, GroqClientError):
        if exception.status_code in (400, 401, 403, 413):
            return False
        if exception.status_code == 429 or (exception.status_code and exception.status_code >= 500):
            return True

    msg = str(exception).lower()
    return bool("timeout" in msg or "connection" in msg or "network" in msg)


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
    stop: list[str] | None = None,
    reasoning_effort: Literal["none", "default", "low", "medium", "high"] | None = None,
    tools: list[ChatCompletionToolParam] | None = None,
) -> Any:
    """Unified wrapper for Groq API calls with professional resilience."""
    if not settings.groq_api_key:
        msg = "Missing Groq API key"
        raise GroqClientError(msg, status_code=401)

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            default_headers={"Groq-Model-Version": "latest"},
        )

        return client.chat.completions.create(
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
    except Exception as e:
        msg = str(e)
        if "413" in msg or "request_too_large" in msg or "Request Entity Too Large" in msg:
            msg = f"Request too large: {msg}"
            raise GroqClientError(msg, status_code=413)

        status_code = None
        if isinstance(e, APIStatusError) or hasattr(e, "status_code"):
            status_code = e.status_code
        elif "HTTP" in msg:
            match = re.search(r"HTTP (\d{3})", msg)
            if match:
                status_code = int(match.group(1))

        msg = f"Groq API error: {msg}"
        raise GroqClientError(msg, status_code=status_code)


def call_groq_api_with_fallback(
    models: list[str],
    messages: list[ChatCompletionMessageParam],
    temperature: float = 1.0,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    stream: bool = False,
    stop: list[str] | None = None,
    reasoning_effort: Literal["none", "default", "low", "medium", "high"] | None = None,
    tools: list[ChatCompletionToolParam] | None = None,
) -> Any:
    """Try models in order, falling back to the next on retryable errors.

    Iterates through ``models``, calling :func:`call_groq_api` for each.
    If a model fails with a retryable error (413, 429, 5xx, timeout, network),
    logs the failure and tries the next model. Fatal errors (401, 403) fail
    immediately. If all models are exhausted, raises the last error.
    """
    if not models:
        msg = "No models provided for fallback chain"
        raise GroqClientError(msg, status_code=400)

    last_error: Exception | None = None
    for model in models:
        try:
            return call_groq_api(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=stream,
                stop=stop,
                reasoning_effort=reasoning_effort,
                tools=tools,
            )
        except GroqClientError as e:
            # Fatal errors — fail immediately, don't fall back
            if e.status_code in (400, 401, 403):
                raise
            # Retryable errors — log and try next model
            logger.warning(
                "Groq model %s failed (status=%s): %s. Falling back...",
                model,
                e.status_code,
                e,
            )
            last_error = e
        except Exception as e:
            logger.warning(
                "Groq model %s failed unexpectedly: %s. Falling back...",
                model,
                e,
            )
            last_error = e

    # All models exhausted
    if isinstance(last_error, GroqClientError):
        raise last_error
    msg = f"All models in fallback chain failed: {last_error or 'unknown error'}"
    raise GroqClientError(msg, status_code=503)


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
