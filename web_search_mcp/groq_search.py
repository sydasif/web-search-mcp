"""Groq browse — interactive multi-page web browsing via Groq's built-in tool."""

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

SupportedModel = Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


def browse(
    query: str,
    model: SupportedModel = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Browse the web interactively via Groq — navigates pages like a human.

    Unlike traditional web search which returns raw links, this tool reads
    multiple pages and returns synthesized information. Use for deep research
    on a specific question. For raw search results, use web_search instead.

    Args:
        query: Search question or topic (e.g. "What are the latest features in Python 3.13?").
        model: Groq model to use ('openai/gpt-oss-20b' is faster; 'openai/gpt-oss-120b' has larger 131K context).
        reasoning_effort: Reasoning intensity ('low' for quick answers, 'high' for deep multi-page exploration).

    Returns:
        Combined results from multiple web sources, or ErrorResponse on failure.

    Examples:
        Use when: you need to compare information across multiple pages
        Use when: the question requires reading and synthesizing from several sources
        Don't use when: you just need quick search result links (use web_search instead)

    Error Handling:
        - Empty query: Returns ErrorResponse with suggested fix
        - Missing API key: Returns clear auth configuration error
        - Groq API error: Returns details with error message for diagnostics
    """
    if not query.strip():
        return format_empty_query_error()

    if not settings.groq_api_key:
        return format_auth_error()

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
            return format_empty_response_error("Groq browse")
        return content
    except Exception as e:
        logger.error("Groq browse failed (%s): %s", model, e)
        return format_error(
            f"Groq browse failed ({model})",
            f"{e}. Try switching to a different model (e.g. openai/gpt-oss-120b) or use web_search instead.",
        )
