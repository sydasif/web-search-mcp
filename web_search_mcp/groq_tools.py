"""Domain logic for Groq-powered web tools.
Consolidates browse, research, and page analysis tools.
"""

import logging
from typing import Literal

from tenacity import RetryError
from .groq_client import call_groq_api, truncate_query, GroqClientError
from .models import ErrorResponse
from .utils import (
    format_auth_error,
    format_empty_query_error,
    format_empty_response_error,
    format_error,
)

logger = logging.getLogger("web-search-mcp")

# Model Type Aliases
SupportedModel = Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
CompoundModel = Literal["groq/compound", "groq/compound-mini"]
DEFAULT_COMPOUND_MODEL: CompoundModel = "groq/compound-mini"


def _unwrap_error(e: Exception) -> Exception:
    """Unwrap tenacity.RetryError to get the original underlying exception."""
    if isinstance(e, RetryError):
        # .exception() returns the original exception or None, avoiding the re-raise of .result()
        return e.last_attempt.exception() or e
    return e


def browse(
    query: str,
    model: SupportedModel = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Browse the web interactively via Groq — navigates pages like a human."""
    if not query.strip():
        return format_empty_query_error()

    try:
        response = call_groq_api(
            messages=[{"role": "user", "content": query}],
            model=model,
            reasoning_effort=reasoning_effort,
            tools=[{"type": "browser_search"}],
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq browse")
        return content
    except Exception as e:
        err = _unwrap_error(e)
        if isinstance(err, GroqClientError) and err.status_code == 401:
            return format_auth_error()

        logger.error("Groq browse failed (%s): %s", model, err)
        return format_error(
            f"Groq browse failed ({model})",
            f"{err}. Try switching to a different model or use web_search instead.",
        )


def research(
    query: str,
    model: CompoundModel = DEFAULT_COMPOUND_MODEL,
) -> str | ErrorResponse:
    """Research a topic using Groq's Compound system — auto-selects search and tools."""
    if not query.strip():
        return format_empty_query_error()

    safe_query = truncate_query(query)

    try:
        response = call_groq_api(
            messages=[{"role": "user", "content": safe_query}],
            model=model,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq research")
        return content
    except Exception as e:
        err = _unwrap_error(e)
        if isinstance(err, GroqClientError):
            if err.status_code == 401:
                return format_auth_error()
            if err.status_code == 413:
                logger.error("Groq research request too large (%s): %s", model, err)
                return format_error(
                    f"Groq's internal search limit exceeded ({model})",
                    "The request exceeded Groq's web_search payload limit. "
                    "Try a shorter, more focused query, or use web_search for raw results.",
                )

        logger.error("Groq research failed (%s): %s", model, err)
        return format_error(
            f"Groq research failed ({model})",
            f"{err}. Try using web_search for raw results or groq_analyze_page for a specific URL.",
        )


def analyze_page(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: CompoundModel = DEFAULT_COMPOUND_MODEL,
) -> str | ErrorResponse:
    """Analyze a web page via Groq Compound — fetches and interprets content."""
    if not url.strip():
        return format_error(
            "URL cannot be empty",
            "Provide a valid URL to visit. Example: 'https://example.com/article'",
        )

    safe_query = truncate_query(query)

    try:
        response = call_groq_api(
            messages=[{"role": "user", "content": f"{safe_query}\n\n{url}"}],
            model=model,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq analyze page")
        return content
    except Exception as e:
        err = _unwrap_error(e)
        if isinstance(err, GroqClientError):
            if err.status_code == 401:
                return format_auth_error()
            if err.status_code == 413:
                logger.error("Groq analyze page request too large (%s): %s", model, err)
                return format_error(
                    f"Page too large for Groq's internal limit ({model})",
                    "The request exceeded Groq's internal payload limit. "
                    "Try using fetch_page to get raw content first, or use a more focused query.",
                )

        logger.error("Groq analyze page failed (%s): %s", model, err)
        return format_error(
            f"Groq analyze page failed ({model})",
            f"{err}. Try using fetch_page to get raw content instead.",
        )
