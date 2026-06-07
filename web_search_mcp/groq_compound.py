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


def _get_client() -> Groq:
    """Create a Groq client with the latest system version header."""
    return Groq(
        api_key=settings.groq_api_key,
        default_headers={"Groq-Model-Version": "latest"},
    )


def research(
    query: str,
    model: CompoundModel = "groq/compound",
) -> str | ErrorResponse:
    """Research a topic using Groq's Compound system — auto-selects search and tools.

    Compound analyzes your question and decides which built-in tools to use
    (web_search, visit_website, etc.), performing multi-step research server-side.

    Use this AFTER web_search to validate, deep-dive, or expand on initial results.
    For quick raw search results, use web_search instead to save tokens.

    Args:
        query: Research question or topic for deep investigation.
        model: Compound system to use. 'groq/compound' supports up to 10 tool calls;
               'groq/compound-mini' has ~3x lower latency but limits to 1 tool call.

    Returns:
        Synthesized research results with citations.

    Examples:
        Use when: you have initial search results and need to validate or expand
        Use when: you need a comprehensive answer that requires multiple searches
        Don't use when: you just need a quick link lookup (use web_search instead)

    Error Handling:
        - Empty query: Returns ErrorResponse with suggested fix
        - Missing API key: Returns clear auth configuration error
        - Compound API error: Returns details with suggested alternatives
    """
    if not query.strip():
        return format_empty_query_error()

    if not settings.groq_api_key:
        return format_auth_error()

    try:
        client = _get_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": query}],
            model=model,
            temperature=1,
            max_completion_tokens=4096,
            top_p=1,
            stream=False,
            stop=None,
            compound_custom={
                "tools": {
                    "enabled_tools": ["web_search"],
                }
            },
        )
        content = response.choices[0].message.content
        if not content:
            return format_empty_response_error("Groq research")
        return content
    except Exception as e:
        logger.error("Groq research failed (%s): %s", model, e)
        return format_error(
            f"Groq research failed ({model})",
            f"{e}. Try using web_search for raw results or groq_analyze_page if you need to examine a specific URL.",
        )


def analyze_page(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: CompoundModel = "groq/compound",
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
        model: Compound system to use. 'groq/compound' for full analysis,
               'groq/compound-mini' for faster results with less depth.

    Returns:
        AI analysis based on the visited page content.

    Examples:
        Use when: you have a URL and need to answer specific questions about its content
        Use when: you need to extract structured information from a page
        Don't use when: you just need raw text content (use fetch_page instead)

    Error Handling:
        - Empty URL: Returns ErrorResponse with suggested fix
        - Missing API key: Returns clear auth configuration error
        - Compound API error: Returns details with suggested alternatives
    """
    if not url.strip():
        return format_error(
            "URL cannot be empty",
            "Provide a valid URL to visit. Example: 'https://example.com/article'",
        )

    if not settings.groq_api_key:
        return format_auth_error()

    try:
        client = _get_client()
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": f"{query}\n\n{url}"}],
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
        logger.error("Groq analyze page failed (%s): %s", model, e)
        return format_error(
            f"Groq analyze page failed ({model})",
            f"{e}. Try using fetch_page to get raw content instead, or check that the URL is publicly accessible.",
        )
