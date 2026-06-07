"""Groq Compound system tools — research and page analysis via Groq's Compound AI system."""

import logging
from typing import Literal

from groq import Groq

from .config import settings
from .models import ErrorResponse
from .utils import (
    format_auth_error,
    format_empty_query_error,
    format_empty_response_error,
    format_error,
)

logger = logging.getLogger("web-search-mcp")

CompoundModel = Literal["groq/compound", "groq/compound-mini"]

# Default to compound-mini for lower latency and single-tool reliability.
# The full compound model supports up to 10 tool calls but may hit
# Groq's internal request-body size limit (~4 KB) when web_search results
# are included in the payload.
DEFAULT_COMPOUND_MODEL: CompoundModel = "groq/compound-mini"

# Groq's internal web_search tool has a ~4 KB request-body size limit.
# Queries exceeding this after URL-encoding trigger HTTP 413. Keep queries
# well under this ceiling.
_MAX_QUERY_BYTES = 3000


def _get_client() -> Groq:
    """Create a Groq client with the latest system version header."""
    return Groq(
        api_key=settings.groq_api_key,
        default_headers={"Groq-Model-Version": "latest"},
    )


def _truncate_query(query: str, max_bytes: int = _MAX_QUERY_BYTES) -> str:
    """Truncate a query to stay within Groq's internal request-body size limit.

    Groq's compound web_search tool enforces a ~4 KB request-body limit.
    Non-ASCII characters expand during URL-encoding (e.g. 'é' → '%C3%A9'),
    so we truncate by byte length with a safety margin.

    Args:
        query: The research query string.
        max_bytes: Maximum byte length (default 3000, safely under 4 KB).

    Returns:
        The query, truncated if necessary, with trailing whitespace stripped.
    """
    query = " ".join(query.split())
    if len(query.encode("utf-8")) <= max_bytes:
        return query

    # Binary-search for the safe cut point to avoid splitting mid-character
    lo, hi = 0, len(query)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(query[:mid].encode("utf-8")) <= max_bytes:
            lo = mid
        else:
            hi = mid - 1

    truncated = query[:lo].rstrip()
    logger.warning(
        "Query truncated from %d to %d bytes to stay within Groq request-body limit",
        len(query.encode("utf-8")),
        len(truncated.encode("utf-8")),
    )
    return truncated


def _is_request_too_large(exc: Exception) -> bool:
    """Check if an exception is a Groq 413 Request Entity Too Large error."""
    msg = str(exc)
    return "413" in msg or "request_too_large" in msg or "Request Entity Too Large" in msg


def research(
    query: str,
    model: CompoundModel = DEFAULT_COMPOUND_MODEL,
) -> str | ErrorResponse:
    """Research a topic using Groq's Compound system — auto-selects search and tools.

    Compound analyzes your question and decides which built-in tools to use
    (web_search, visit_website, etc.), performing multi-step research server-side.

    Use this AFTER web_search to validate, deep-dive, or expand on initial results.
    For quick raw search results, use web_search instead to save tokens.

    Note: Compound models auto-select tools. Long queries may be internally
    truncated by the server to fit Groq's web_search request-body limit (~4 KB).
    Keep queries concise for best results.

    Args:
        query: Research question or topic for deep investigation.
        model: Compound system to use. 'groq/compound-mini' (default) has ~3x
               lower latency but limits to 1 tool call; 'groq/compound' supports
               up to 10 tool calls.

    Returns:
        Synthesized research results with citations.

    Examples:
        Use when: you have initial search results and need to validate or expand
        Use when: you need a comprehensive answer that requires multiple searches
        Don't use when: you just need a quick link lookup (use web_search instead)

    Error Handling:
        - Empty query: Returns ErrorResponse with suggested fix
        - Missing API key: Returns clear auth configuration error
        - Request too large (413): Query was too long; suggests shorter query
        - Compound API error: Returns details with suggested alternatives
    """
    if not query.strip():
        return format_empty_query_error()

    if not settings.groq_api_key:
        return format_auth_error()

    safe_query = _truncate_query(query)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": safe_query}],
            model=model,
            temperature=1,
            max_completion_tokens=4096,
            top_p=1,
            stream=False,
            stop=None,
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq research")
        return content
    except Exception as e:
        if _is_request_too_large(e):
            logger.error("Groq research request too large (%s): %s", model, e)
            return format_error(
                f"Groq's internal search limit exceeded ({model})",
                (
                    "The request exceeded Groq's web_search payload limit. This can "
                    "happen with long queries or when the internal search returns large "
                    "results. Try: (1) a shorter, more focused query like 'latest Python "
                    "3.13 features', or (2) use web_search for raw results without this "
                    "size restriction."
                ),
            )
        logger.error("Groq research failed (%s): %s", model, e)
        return format_error(
            f"Groq research failed ({model})",
            f"{e}. Try using web_search for raw results or groq_analyze_page if you "
            "need to examine a specific URL.",
        )


def analyze_page(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: CompoundModel = DEFAULT_COMPOUND_MODEL,
) -> str | ErrorResponse:
    """Analyze a web page via Groq Compound — fetches and interprets content.

    Compound visits the URL server-side and returns an AI analysis of the page
    content. Use this AFTER fetch_page when you need interpretation or answers
    to specific questions about the content.

    For raw page content without interpretation costs, use fetch_page instead.

    Args:
        url: The URL to visit and analyze (e.g. 'https://docs.python.org/3/whatsnew/3.13.html').
        query: What to do with the page content (e.g. 'Extract the table of contents',
               'Find the author's main argument', 'List all API changes').
        model: Compound system to use. 'groq/compound-mini' (default) is more
               reliable; 'groq/compound' may hit request-body limits on large pages.

    Returns:
        AI analysis based on the visited page content.

    Examples:
        Use when: you have a URL and need to answer specific questions about its content
        Use when: you need to extract structured information from a page
        Don't use when: you just need raw text content (use fetch_page instead)

    Error Handling:
        - Empty URL: Returns ErrorResponse with suggested fix
        - Missing API key: Returns clear auth configuration error
        - Request too large (413): Page content too large; suggests fetch_page
        - Compound API error: Returns details with suggested alternatives
    """
    if not url.strip():
        return format_error(
            "URL cannot be empty",
            "Provide a valid URL to visit. Example: 'https://example.com/article'",
        )

    if not settings.groq_api_key:
        return format_auth_error()

    safe_query = _truncate_query(query)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": f"{safe_query}\n\n{url}"}],
            model=model,
            temperature=1,
            max_completion_tokens=4096,
            top_p=1,
            stream=False,
            stop=None,
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq analyze page")
        return content
    except Exception as e:
        if _is_request_too_large(e):
            logger.error("Groq analyze page request too large (%s): %s", model, e)
            return format_error(
                f"Page too large for Groq's internal limit ({model})",
                (
                    "The request exceeded Groq's internal payload limit. This can "
                    "happen with large pages. Try: (1) use fetch_page to get raw "
                    "content, then ask a specific question, or (2) use a shorter, "
                    "more focused query like 'list the main topics on this page'."
                ),
            )
        logger.error("Groq analyze page failed (%s): %s", model, e)
        return format_error(
            f"Groq analyze page failed ({model})",
            f"{e}. Try using fetch_page to get raw content instead, or check that "
            "the URL is publicly accessible.",
        )
