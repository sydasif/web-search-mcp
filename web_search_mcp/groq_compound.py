"""Groq Compound system tools — auto-selecting web search and website visiting via Groq's Compound AI system."""

import logging
from typing import Literal

from groq import Groq

from .config import settings
from .models import ErrorResponse
from .utils import format_error

logger = logging.getLogger("web-search-mcp")

CompoundModel = Literal["groq/compound", "groq/compound-mini"]


def _get_client() -> Groq:
    """Create a Groq client with the latest system version header."""
    return Groq(
        api_key=settings.groq_api_key,
        default_headers={"Groq-Model-Version": "latest"},
    )


def compound_search(
    query: str,
    model: CompoundModel = "groq/compound",
) -> str | ErrorResponse:
    """Search the web using Groq's Compound system.

    Compound auto-selects the optimal built-in tool(s) for the query,
    performing multi-step research (search → read → synthesize).

    Use this after web_search to validate, deep-dive, or expand on
    initial results.

    Args:
        query: Search question or topic for deep research.
        model: Compound system to use ('groq/compound' or 'groq/compound-mini').

    Returns:
        Synthesized research results with citations.
    """
    if not query.strip():
        return format_error("Query cannot be empty", "Provide a non-empty search query.")

    if not settings.groq_api_key:
        return format_error(
            "Groq API key not configured",
            "Set SEARCH_MCP_GROQ_API_KEY env var or add it to your MCP config.",
        )

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
            return format_error("Groq returned empty content", "The model produced no response.")
        return content
    except Exception as e:
        logger.error(f"Groq compound search failed ({model}): {e}")
        return format_error("Groq compound search failed", str(e))


def visit_website(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: CompoundModel = "groq/compound",
) -> str | ErrorResponse:
    """Visit and analyze a specific web page using Groq's Compound system.

    Compound fetches the URL server-side and returns an AI analysis of
    the page content. Use this after fetch_page to validate, interpret,
    or answer specific questions about the page content.

    Args:
        url: The URL to visit and analyze.
        query: What to do with the page content (default: summarize key points).
        model: Compound system to use ('groq/compound' or 'groq/compound-mini').

    Returns:
        AI analysis based on the visited page content.
    """
    if not url.strip():
        return format_error("URL cannot be empty", "Provide a valid URL to visit.")

    if not settings.groq_api_key:
        return format_error(
            "Groq API key not configured",
            "Set SEARCH_MCP_GROQ_API_KEY env var or add it to your MCP config.",
        )

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
            return format_error("Groq returned empty content", "The model produced no response.")
        return content
    except Exception as e:
        logger.error(f"Groq visit website failed ({model}): {e}")
        return format_error("Groq visit website failed", str(e))
