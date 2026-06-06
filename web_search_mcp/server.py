import logging
from typing import Literal

from fastmcp import FastMCP

from .models import SearchRequest, FetchOutputFormat, SearchResponse, PageResponse, ErrorResponse
from .search import ddg_search, format_search_results_markdown
from .utils import format_error
from .reader import fetch_page as _fetch_page
from .groq_search import browse as _groq_browse
from .groq_compound import research as _groq_research
from .groq_compound import analyze_page as _groq_analyze_page

# Set up logging
logger = logging.getLogger("web-search-mcp")

mcp = FastMCP("Web Search Tools")

# ─────────────────────────────────────────────────────────────
# DuckDuckGo tools — fast, free, raw data
# Best for: quick lookups, high-volume searches, pagination
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="web_search",
    annotations={
        "title": "Search the web via DuckDuckGo",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def web_search(
    query: str,
    search_type: Literal["text", "news"] = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: Literal["moderate", "off", "on"] = "moderate",
    page: int = 1,
    backend: Literal["auto", "legacy", "api"] = "auto",
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search the web via DuckDuckGo — free, fast, returns raw structured results.

    Role: Discovery. Use this as your first-pass search for broad coverage.
    Workflow: Feed results into groq_research for deep validation, or
    fetch_page to get full page content. Alternative: groq_research
    provides a synthesized answer instead of raw links.

    Args:
        query: Search query string
        search_type: Type of search ('text' or 'news')
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')
        response_format: Output format - 'markdown' for human-readable, 'json' for structured data

    Returns:
        str: Markdown-formatted search results (when response_format="markdown")
        SearchResponse: Raw search results (when response_format="json")
        ErrorResponse: Error response if applicable
    """
    try:
        req = SearchRequest(
            query=query,
            search_type=search_type,
            max_results=max_results,
            time_range=time_range,
            region=region,
            safesearch=safesearch,
            page=page,
            backend=backend,
            response_format=response_format,
        )
        result = ddg_search(req)
        if response_format == "markdown":
            # We cast result to SearchResponse | dict here for the formatter
            return format_search_results_markdown(result)  # type: ignore
        return result
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return format_error(
            "DuckDuckGo search failed",
            f"{e}. Try reducing max_results, switching search_type, or using a more specific query.",
        )


@mcp.tool(
    name="fetch_page",
    annotations={
        "title": "Extract text content from a URL",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def fetch_page(
    url: str,
    output_format: FetchOutputFormat = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
    backend: Literal["httpx", "curl", "auto"] = "auto",
) -> PageResponse | ErrorResponse:
    """Extract raw text content from a URL — fast, free, full control.

    Role: Retrieval. Use this when you need the actual page content (not a
    summary). Supports bot-detection bypass and multiple output formats.
    Workflow: Pipe the content into groq_analyze_page for AI interpretation.
    Alternative: groq_analyze_page fetches AND interprets in one step, but
    costs tokens and gives you no raw content.

    Args:
        url: The URL to fetch and extract content from
        output_format: Format for extracted content ('csv', 'html', 'json', 'markdown', 'python', 'txt', 'xml', 'xmltei')
        include_metadata: Whether to include document metadata (title, author, date, etc.)
        include_tables: Whether to include table content in extraction
        include_comments: Whether to include comment content in extraction
        include_images: Whether to include image descriptions in extraction
        deduplicate: Whether to remove duplicated content
        max_length: Maximum length of content to return (default 15000)
        timeout: Request timeout in seconds (default 30)
        backend: HTTP backend to use ('httpx' for lightweight, 'curl' to bypass bot detection, 'auto' to try httpx first then fallback to curl)
    """
    return _fetch_page(
        url=url,
        output_format=output_format,
        include_metadata=include_metadata,
        include_tables=include_tables,
        include_comments=include_comments,
        include_images=include_images,
        deduplicate=deduplicate,
        max_length=max_length,
        timeout=timeout,
        backend=backend,
    )  # type: ignore


@mcp.tool(
    name="search_docs",
    annotations={
        "title": "Search a domain for technical documentation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_docs(query: str, domain: str = "docs.python.org") -> SearchResponse | ErrorResponse:
    """Search a specific domain for technical documentation via DuckDuckGo.

    Role: Targeted discovery. Use this when you know which site has the
    answer (e.g. docs.python.org, react.dev). Faster and more precise than
    general web_search. Alternative: groq_browse does interactive browsing
    for deeper research on a specific site.

    Args:
        query: What you're looking for
        domain: The domain to search (e.g. 'docs.python.org', 'stackoverflow.com')

    Returns:
        Search results from the specified domain
    """
    enhanced_query = f"site:{domain} {query}"

    try:
        req = SearchRequest(
            query=enhanced_query,
            search_type="text",
            max_results=5,
        )
        return ddg_search(req)
    except Exception as e:
        logger.error(f"Domain search failed for query '{query}' on domain '{domain}': {e}")
        return format_error("Search failed", str(e))


# ─────────────────────────────────────────────────────────────
# Groq GPT-OSS tools — interactive browser search via GPT-OSS models
# Best for: browsing-style search, single-page deep reads
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="groq_browse",
    annotations={
        "title": "Browse the web interactively via Groq",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_browse(
    query: str,
    model: Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"] = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Interactive browser search via Groq — navigates websites like a human.

    Role: Deep browsing. Use this when you need multi-page context or
    the site requires interactive navigation. Alternative: search_docs for
    simple single-domain searches, or groq_research for auto-selecting
    the best combination of search and page reading.

    Args:
        query: Search question or topic
        model: Groq model to use ('openai/gpt-oss-20b' or 'openai/gpt-oss-120b')
        reasoning_effort: Reasoning intensity ('low', 'medium', 'high').
            'low' balances quality vs token cost; 'high' explores more pages.

    Returns:
        Combined results from multiple web sources
    """
    return _groq_browse(query=query, model=model, reasoning_effort=reasoning_effort)


# ─────────────────────────────────────────────────────────────
# Groq Compound tools — auto-selecting AI research system
# Best for: deep research, validation, multi-step synthesis
# Costs tokens — use DDG tools for quick lookups
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="groq_research",
    annotations={
        "title": "Deep research via Groq Compound",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_research(
    query: str,
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound",
) -> str | ErrorResponse:
    """Deep research via Groq Compound — auto-selects search, browsing, and tools.

    Role: Validation & synthesis. Use this AFTER web_search to validate,
    deep-dive, or expand on initial results. Compound decides whether to
    search, visit pages, or use other tools to answer your question.
    Alternative: web_search for fast raw results, groq_browse for a
    simpler interactive browse.

    Args:
        query: Research question or topic for deep investigation
        model: Compound system ('groq/compound' for full, 'groq/compound-mini' for lower latency)

    Returns:
        Synthesized research results from multiple sources
    """
    return _groq_research(query=query, model=model)


@mcp.tool(
    name="groq_analyze_page",
    annotations={
        "title": "Analyze a web page via Groq Compound",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_analyze_page(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound",
) -> str | ErrorResponse:
    """Visit and analyze a URL via Groq Compound — fetches AND interprets.

    Role: Interpretation. Use this AFTER fetch_page when you need AI analysis
    of the content (e.g. "Find the argument for X", "Extract the data table").
    Alternative: fetch_page gives you raw content for free — use that when
    you just need to read the text yourself.

    Args:
        url: The URL to visit and analyze
        query: What to do with the page content (default: summarize key points)
        model: Compound system ('groq/compound' for full, 'groq/compound-mini' for lower latency)

    Returns:
        AI analysis based on the visited page content
    """
    return _groq_analyze_page(url=url, query=query, model=model)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
