"""Domain logic for Groq-powered tools.
Provides interactive browsing via GPT-OSS models and page analysis via Compound API.
"""

import logging
from typing import Literal

from .._models import ErrorResponse
from .._utils import (
    format_auth_error,
    format_empty_query_error,
    format_empty_response_error,
    format_error,
)
from .groq_client import GroqClientError, call_groq_api_with_fallback, truncate_query

logger = logging.getLogger(__name__)


def search(
    query: str,
    model: Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"] = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Interactive web browsing via GPT-OSS models — navigates pages step by step.

    GPT-OSS models use explicit ``browser_search`` tool configuration to interactively
    browse and explore web pages. Best for multi-step tutorials, JS-heavy pages,
    and situations where you need the model to click through documentation.

    **Fallback:** Tries the selected model first. If it fails with a retryable
    error (413, 429, 5xx), automatically falls back to the other GPT-OSS model.
    """
    if not query.strip():
        return format_empty_query_error()

    # Build fallback chain: prefer the user's choice, then try the other
    all_models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    fallback_chain = [model] + [m for m in all_models if m != model]

    try:
        response = call_groq_api_with_fallback(
            models=fallback_chain,
            messages=[{"role": "user", "content": query}],
            max_tokens=4096,
            reasoning_effort=reasoning_effort,
            tools=[{"type": "browser_search"}],
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq browse search")
        return content
    except Exception as e:
        if isinstance(e, GroqClientError) and e.status_code == 401:
            return format_auth_error()

        logger.exception("Groq browse search failed: %s", e)
        return format_error(
            "All Groq browse models failed",
            f"{e}. Try using web_search for raw results or groq_analyze for page analysis.",
        )


def groq_analyze(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound-mini",
) -> str | ErrorResponse:
    """Analyze a web page via Groq Compound — fetches and interprets content.

    **Fallback:** Tries the selected model first. If it fails with a retryable
    error (413, 429, 5xx), automatically falls back to the other compound model.
    """
    if not url.strip():
        return format_error(
            "URL cannot be empty",
            "Provide a valid URL to visit. Example: 'https://example.com/article'",
        )

    safe_query = truncate_query(query)

    # Build fallback chain: prefer the user's choice, then try the other
    all_models = ["groq/compound-mini", "groq/compound"]
    fallback_chain = [model] + [m for m in all_models if m != model]

    try:
        response = call_groq_api_with_fallback(
            models=fallback_chain,
            messages=[{"role": "user", "content": f"{safe_query}\n\n{url}"}],
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq analyze")
        return content
    except Exception as e:
        if isinstance(e, GroqClientError) and e.status_code == 401:
            return format_auth_error()

        logger.exception("Groq analyze failed: %s", e)
        return format_error(
            "All Groq analyze models failed",
            f"{e}. Try using fetch_page to get raw content instead.",
        )
