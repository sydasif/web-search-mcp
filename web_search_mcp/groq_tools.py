"""Domain logic for Groq-powered web tools.
Provides unified search and page analysis via Groq's API.
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

logger = logging.getLogger(__name__)

# Model Type Aliases
CompoundModel = Literal["groq/compound", "groq/compound-mini"]
DEFAULT_COMPOUND_MODEL: CompoundModel = "groq/compound-mini"


def _unwrap_error(e: BaseException) -> BaseException:
    """Unwrap tenacity.RetryError to get the original underlying exception."""
    if isinstance(e, RetryError):
        # .exception() returns the original exception or None, avoiding the re-raise of .result()
        return e.last_attempt.exception() or e
    return e


# Combined model type: GPT-OSS for browsing, Compound for auto-tool-selection
GroqModel = Literal[
    "openai/gpt-oss-20b", "openai/gpt-oss-120b", "groq/compound", "groq/compound-mini"
]

# Models that use browser_search tool (GPT-OSS models)
_BROWSE_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}


def search(
    query: str,
    model: GroqModel = "groq/compound-mini",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """AI-powered web search via Groq — browse interactively or auto-research.

    Role: AI-assisted search. Use when you need the model to actively browse
    and synthesize information from multiple pages.

    Two modes based on model selection:
    - GPT-OSS models (openai/gpt-oss-20b/120b): Interactive browsing with
      explicit page navigation. Use reasoning_effort to control depth.
    - Compound models (groq/compound/compound-mini): Auto-selects search tools
      and synthesis strategy. compound-mini is faster (1 tool call),
      compound supports up to 10 tool calls.

    Alternative: web_search for raw DDG results (free, no tokens).
    """
    if not query.strip():
        return format_empty_query_error()

    is_browse = model in _BROWSE_MODELS

    try:
        if is_browse:
            response = call_groq_api(
                messages=[{"role": "user", "content": query}],
                model=model,
                reasoning_effort=reasoning_effort,
                tools=[{"type": "browser_search"}],
            )
        else:
            safe_query = truncate_query(query)
            response = call_groq_api(
                messages=[{"role": "user", "content": safe_query}],
                model=model,
                max_tokens=4096,
            )

        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq search")
        return content
    except Exception as e:
        err = _unwrap_error(e)
        if isinstance(err, GroqClientError):
            if err.status_code == 401:
                return format_auth_error()
            if err.status_code == 413:
                logger.error("Groq search request too large (%s): %s", model, err)
                return format_error(
                    f"Request too large for {model}",
                    "The request exceeded Groq's limit. Try a shorter query or use web_search for raw results.",
                )

        logger.error("Groq search failed (%s): %s", model, err)
        return format_error(
            f"Groq search failed ({model})",
            f"{err}. Try using web_search for raw results or groq_analyze for a specific URL.",
        )


def groq_analyze(
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
            return format_empty_response_error("Groq analyze")
        return content
    except Exception as e:
        err = _unwrap_error(e)
        if isinstance(err, GroqClientError):
            if err.status_code == 401:
                return format_auth_error()
            if err.status_code == 413:
                logger.error("Groq analyze request too large (%s): %s", model, err)
                return format_error(
                    f"Page too large for Groq's internal limit ({model})",
                    "The request exceeded Groq's internal payload limit. "
                    "Try using fetch_page to get raw content first, or use a more focused query.",
                )

        logger.error("Groq analyze failed (%s): %s", model, err)
        return format_error(
            f"Groq analyze failed ({model})",
            f"{err}. Try using fetch_page to get raw content instead.",
        )
