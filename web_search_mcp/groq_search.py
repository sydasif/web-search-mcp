"""Groq browser search — interactive multi-page web browsing via Groq's built-in tool."""

import logging
from typing import Literal

from groq import Groq

from .config import settings
from .models import ErrorResponse
from .utils import format_error

logger = logging.getLogger("web-search-mcp")

SupportedModel = Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


def web_search(
    query: str,
    model: SupportedModel = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Perform an interactive browser search using Groq's built-in tool.

    Unlike traditional web search, this navigates websites like a human
    for more comprehensive results. Server-side execution — no browser needed.

    Args:
        query: Search question or topic.
        model: Groq model to use ('openai/gpt-oss-20b' or 'openai/gpt-oss-120b').
        reasoning_effort: Reasoning intensity ('low', 'medium', 'high').
            'low' balances quality vs token cost; 'high' explores more pages.

    Returns:
        Combined results from multiple web sources, or ErrorResponse on failure.
    """
    if not query.strip():
        return format_error("Query cannot be empty", "Provide a non-empty search query.")

    if not settings.groq_api_key:
        return format_error(
            "Groq API key not configured",
            "Set SEARCH_MCP_GROQ_API_KEY env var or add it to your MCP config.",
        )

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": query}],
            model=model,
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            stream=False,
            stop=None,
            reasoning_effort=reasoning_effort,
            tools=[{"type": "browser_search"}],
        )
        content = response.choices[0].message.content
        if not content:
            return format_error("Groq returned empty content", "The model produced no response.")
        return content
    except Exception as e:
        logger.error(f"Groq browser search failed ({model}): {e}")
        return format_error("Groq browser search failed", str(e))
