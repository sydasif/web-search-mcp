from __future__ import annotations

import logging
from typing import Any, Literal, cast

from fastmcp import FastMCP

from ._models import ErrorResponse, FetchOutputFormat, PageResponse, SearchRequest, SearchResponse
from ._models.types import Depth, ResponseFormat
from ._utils import format_error
from .search.ddg import ddg_search, format_search_results_markdown
from .search.ddg import fetch_page as _fetch_page
from .search.exa import exa_search as _exa_search
from .social.github import (
    enrich_with_comments as _enrich_gh,
)
from .social.github import (
    format_github_markdown as _format_gh_markdown,
)
from .social.github import (
    get_github_issue as _get_github_issue,
)
from .social.github import (
    search_github as _search_gh,
)
from .social.hackernews import enrich_top_stories as _enrich_hn
from .social.hackernews import format_hackernews_markdown as _format_hn_markdown
from .social.hackernews import search_hackernews as _search_hn
from .social.reddit import reddit_search_tool as _reddit_search_tool
from .social.x import format_x_markdown as _format_x_markdown
from .social.x import search_x as _search_x
from .tools.arxiv import SortCriterion
from .tools.arxiv import arxiv_search_tool as _arxiv_search_tool
from .tools.wikipedia import wikipedia_search_tool as _wikipedia_search_tool

LOG_FORMAT = "%(levelname)-8s %(name)s %(message)s"


_configured = False


def configure_logging(level: int = logging.DEBUG) -> None:
    """Configure the web-search-mcp logger with a stderr handler.

    Called automatically on first import. Call again with a different level
    (e.g. ``logging.WARNING``) to quiet diagnostics.
    """
    global _configured
    if _configured:
        return
    _configured = True
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    _logger = logging.getLogger("web-search-mcp")
    _logger.addHandler(handler)
    _logger.setLevel(level)


configure_logging()
logger = logging.getLogger(__name__)

mcp = FastMCP("Web Search Tools")

# ─────────────────────────────────────────────────────────────
# DuckDuckGo tools — fast, free, raw data
# Best for: quick lookups, high-volume searches, pagination
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_web",
    annotations={
        "title": "Search the web via DuckDuckGo or Exa",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_web(
    query: str,
    max_results: int = 5,
    search_type: Literal["text", "news"] = "text",
    time_range: str | None = None,
    region: str | None = None,
    domain: str | None = None,
    response_format: ResponseFormat = "markdown",
    provider: Literal["auto", "ddg", "exa"] = "auto",
) -> str | SearchResponse | ErrorResponse:
    """Search the web via DuckDuckGo or Exa — fast, free, returns structured results.

    Role: Discovery. Use this as your first-pass search for broad coverage.
    Workflow: Feed results into fetch_page to get full page content.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        search_type: Type of search ('text' or 'news').
        time_range: Time filter ('d', 'w', 'm', 'y') or None.
        region: Geographic region (e.g. 'us-en', 'uk-en'). DDG: passed directly.
            Exa: converts to two-letter ISO country code (user_location).
        domain: Optional domain to scope results (e.g. 'docs.python.org').
            DDG: adds a site: prefix. Exa: maps to include_domains.
        response_format: Output format - 'markdown' for human-readable, 'json' for structured data
        provider: Search provider ('auto', 'ddg', 'exa'). Default 'auto' tries
            DuckDuckGo first, falls back to Exa if DDG returns an error.

    Returns:
        str: Markdown-formatted search results (when response_format="markdown")
        SearchResponse: Raw search results (when response_format="json")
        ErrorResponse: Error response if applicable

    Examples:
        - "Latest NVIDIA H200 benchmarks"
        - "How to install uv on macOS"
        - "asyncio event loop" with domain="docs.python.org"
        - "useEffect cleanup" with domain="react.dev"

    Error Handling:
        - 429 Too Many Requests: Try reducing max_results or wait 60s.
        - Empty Results: Try a more general query or change search_type.

    """
    try:
        effective_query = f"site:{domain} {query}" if domain else query

        req = SearchRequest(
            query=effective_query,
            search_type=search_type,
            max_results=max_results,
            time_range=time_range,
            region=region,
            provider=provider,
            response_format=response_format,
        )

        def _run_ddg() -> SearchResponse | ErrorResponse:
            return ddg_search(req)

        def _run_exa() -> SearchResponse | ErrorResponse:
            return _exa_search(
                query=query,
                max_results=max_results,
                search_type=search_type,
                time_range=time_range,
                region=region,
                domain=domain,
            )

        if provider == "ddg":
            result = _run_ddg()
        elif provider == "exa":
            result = _run_exa()
        else:  # "auto"
            result = _run_ddg()
            if isinstance(result, ErrorResponse) or (
                isinstance(result, SearchResponse) and result.total_results == 0
            ):
                logger.info("DDG returned no results for %r; falling back to Exa", query)
                result = _run_exa()

        if response_format == "markdown":
            return format_search_results_markdown(result)
        return result
    except Exception as e:
        logger.exception("Search failed")
        return format_error(
            "Search failed",
            f"{e}. Try reducing max_results, switching search_type, "
            "or using a more specific query.",
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
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> PageResponse | ErrorResponse:
    """Extract clean text content from a URL.

    Role: Content retrieval. Use this after search_web to read the full
    page content of a search result. Also works standalone for known URLs.
    Workflow: search_web → pick a URL → fetch_page to get the text.

    Args:
        url: The URL to fetch and extract content from
        output_format: Format for extracted content ('csv', 'html', 'json',
            'markdown', 'python', 'txt', 'xml', 'xmltei')
        include_metadata: Whether to include document metadata (title, author, date, etc.)
        include_tables: Whether to include table content in extraction
        deduplicate: Whether to remove duplicated content
        max_length: Maximum length of content to return (default 15000)
        timeout: Request timeout in seconds (default 30, httpx path only —
            Exa fallback uses the SDK's own timeout)

    Returns:
        PageResponse: Extracted content and metadata
        ErrorResponse: Error response if applicable

    Examples:
        - "https://docs.python.org/3/library/asyncio.html"
        - "https://docs.pydantic.dev/latest/concepts/serialization/" with output_format="markdown"

    Error Handling:
        - Unsupported URL scheme (ftp, file): Returns error
        - Private/internal IP address: Returns error (SSRF protection)
        - HTTP timeout or network error: Returns error with details
        - No readable text found: Returns error (e.g. image-only pages)

    """
    return _fetch_page(
        url=url,
        output_format=output_format,
        include_metadata=include_metadata,
        include_tables=include_tables,
        deduplicate=deduplicate,
        max_length=max_length,
        timeout=timeout,
    )


# ─────────────────────────────────────────────────────────────
# Reddit tools — keyless, free Reddit search
# Best for: community discussions, opinions, real user experiences
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_reddit",
    annotations={
        "title": "Search Reddit via keyless RSS + shreddit enrichment",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_reddit(
    query: str,
    max_results: int = 25,
    time_range: str | None = None,
    depth: Depth = "default",
    subreddits: list[str] | None = None,
    response_format: ResponseFormat = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Reddit via keyless RSS + shreddit enrichment — free, no API key needed.

    Role: Discovery. Use this for Reddit-specific discussions, opinions, and
    community insights. Alternative: search_web for general web results.

    Workflow: Three-tier keyless pipeline:
    - Tier 0: Legacy .json search (often 403, tried once)
    - Tier 1: RSS discovery (load-bearing, robust)
    - Tier 2: Shreddit comment enrichment for top posts

    Args:
        query: Search query string
        max_results: Max results (capped by depth: quick=10, default=25, deep=50)
        time_range: Time filter ('d', 'w', 'm', 'y') — mapped to date range
        depth: Search depth — controls result limits and enrichment
        subreddits: Optional list of subreddit names to target (without r/)
        response_format: Output format ('json' or 'markdown')

    Returns:
        str: Markdown-formatted Reddit posts (when response_format="markdown")
        SearchResponse: Raw Reddit posts with scores and comments (when response_format="json")
        ErrorResponse: Error response if applicable

    Examples:
        - "What are the best mechanical keyboards 2024"
        - "Thoughts on the new Claude 4 models", subreddits=["LocalLLaMA", "ArtificialInteligence"]
        - "How to fix memory leak in Python", depth="deep"

    Error Handling:
        - Reddit 403/429: The free keyless path is rate-limited. Try a
          different query, target specific subreddits, or wait.

    """
    return _reddit_search_tool(
        query=query,
        max_results=max_results,
        time_range=time_range,
        depth=depth,
        subreddits=subreddits,
        response_format=response_format,
    )


# ─────────────────────────────────────────────────────────────
# Hacker News tools — free, tech discourse
# Best for: tech news, startup discussions, developer opinions
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_hackernews",
    annotations={
        "title": "Search Hacker News via Algolia API",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_hackernews(
    query: str,
    max_results: int = 30,
    depth: Depth = "default",
    response_format: ResponseFormat = "markdown",
) -> str | list[dict[str, Any]] | ErrorResponse:
    """Search Hacker News via Algolia API — free, no API key needed.

    Role: Tech discourse. Use this for developer news, startup discussions,
    and technical opinions. Alternative: search_web for general results.

    Args:
        query: Search query string
        max_results: Max results (capped by depth: quick=15, default=30, deep=60)
        depth: Search depth — controls result limits and comment enrichment
        response_format: Output format ('json' or 'markdown')

    Returns:
        str: Markdown-formatted results (when response_format="markdown")
        list: Hacker News stories with engagement scores and optional comments
        ErrorResponse: Error response if applicable

    Examples:
        - "What are people saying about the new Claude models"
        - "Is Rust production-ready in 2026"
        - "Best practices for building MCP servers"

    Error Handling:
        - Empty results: Try a more general query or broaden the search terms.

    """
    if not query or not query.strip():
        return format_error("Query cannot be empty")

    try:
        items = _search_hn(query, depth=depth)[:max_results]
        items = _enrich_hn(items, depth=depth)
        if response_format == "markdown":
            return _format_hn_markdown(items, query)
        return items
    except Exception as e:
        logger.exception("Hacker News search failed")
        return format_error(f"Hacker News search failed: {e}")


# ─────────────────────────────────────────────────────────────
# arXiv tools — free, academic paper search
# Best for: research papers, citations, literature reviews
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_arxiv",
    annotations={
        "title": "Search arXiv for academic papers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: SortCriterion = "relevance",
) -> str | ErrorResponse:
    """Search arXiv for academic papers — free, no API key needed.

    Role: Academic research. Use this to find papers by keyword, author,
    or category. Supports Lucene field prefixes for targeted searches.
    Alternative: search_web for general results.

    Field prefixes:
    - ``all:`` — Search all fields (default)
    - ``ti:`` — Title only
    - ``au:`` — Author name
    - ``abs:`` — Abstract only
    - ``cat:`` — Category (e.g. cat:cs.AI, cat:hep-th, cat:math)

    Args:
        query: Search query with optional field prefixes
               (e.g. "transformer attention", "au:Goodfellow", "cat:cs.AI")
        max_results: Max results to return (default 10, max 50)
        sort_by: Sort criterion ('relevance', 'submitted_date', 'updated_date')

    Returns:
        str: Markdown-formatted list of papers with title, authors, date,
             categories, and abstract excerpt.
        ErrorResponse: Error response if applicable

    Examples:
        - "quantum computing error correction"
        - "au:Yoshua+Bengio AND cat:cs.LG"
        - "cat:cs.AI reinforcement learning"

    Error Handling:
        - Empty query: Returns error message.
        - arXiv API down: arXiv periodically has maintenance. Try again later.

    """
    return _arxiv_search_tool(query=query, max_results=max_results, sort_by=sort_by)


# ─────────────────────────────────────────────────────────────
# Wikipedia tools — free, open encyclopedia
# Best for: factual summaries, background research, citations
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_wikipedia",
    annotations={
        "title": "Search Wikipedia and read articles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_wikipedia(
    query: str,
    max_results: int = 5,
) -> str | ErrorResponse:
    """Search Wikipedia and return the top article with full text + related results.

    Searches Wikipedia via the MediaWiki API, fetches the top article's full
    plain text content (with ``== Section ==`` markers), and lists related
    articles below. No API key required.

    Args:
        query: Search query (e.g. "Python programming language")
        max_results: Max results to show (default 5, max 20)

    Returns:
        str: Markdown-formatted article content with related links.
        ErrorResponse: Error response if applicable

    Examples:
        - "Python programming language"
        - "Albert Einstein"
        - "Quantum computing"

    Error Handling:
        - Empty query: Returns error message
        - No results: Returns "No Wikipedia articles found"
        - Network error: Returns error message

    """
    try:
        return _wikipedia_search_tool(query, max_results=max_results)
    except Exception as e:
        logger.exception("Wikipedia search failed")
        return format_error(f"Wikipedia search failed: {e}")


# ─────────────────────────────────────────────────────────────
# GitHub tools — issues/PRs search, auth via GITHUB_TOKEN or gh
# Best for: code discussions, bug reports, feature requests
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_github",
    annotations={
        "title": "Search GitHub Issues and PRs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_github(
    query: str,
    max_results: int = 30,
    depth: Depth = "default",
    token: str | None = None,
    response_format: ResponseFormat = "markdown",
) -> str | list[dict[str, Any]] | ErrorResponse:
    """Search GitHub Issues and PRs via the GitHub Search API.

    Role: Code & issues. Use this for bug discussions, feature requests,
    and community sentiment on GitHub projects. Alternative: search_web
    for general results, or search_web with domain="docs.python.org" for documentation.

    Note: Requires GITHUB_TOKEN env var or `gh` CLI installed and authenticated.
    Without auth, returns empty results.

    Args:
        query: Search query (e.g. 'uv package manager', 'pydantic v2 migration')
        max_results: Max results (capped by depth: quick=15, default=30, deep=60)
        depth: Search depth — controls result limits and comment enrichment
        token: Optional GitHub token (falls back to GITHUB_TOKEN env or gh CLI)
        response_format: Output format ('json' or 'markdown')

    Returns:
        str: Markdown-formatted results (when response_format="markdown")
        list: GitHub issues/PRs with reactions, labels, and optional comments
        ErrorResponse: Error response if applicable

    Examples:
        - "uv package manager" — find top-voted issues
        - "FastAPI websocket" — find discussions about websockets
        - "pydantic v2 migration" — find migration-related issues/PRs

    Error Handling:
        - No token: Set GITHUB_TOKEN env var or install gh CLI.
        - 403 rate limit: Wait or use a token with higher limits.
        - Empty results: Try a broader query or different keywords.

    """
    if not query or not query.strip():
        return format_error("Query cannot be empty")

    try:
        items = _search_gh(query, depth=depth, token=token)[:max_results]
        items = _enrich_gh(items, depth=depth, token=token)
        if response_format == "markdown":
            return _format_gh_markdown(items, query)
        return items
    except Exception as e:
        logger.exception("GitHub search failed")
        return format_error(f"GitHub search failed: {e}")


# ─────────────────────────────────────────────────────────────
# GitHub Issue/PR thread rendering via gh CLI
# Best for: getting the full conversation context of a specific
# GitHub Issue or PR, with all comments sorted by reactions.
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="get_github_issue",
    annotations={
        "title": "Fetch a GitHub Issue or PR with all comments",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def get_github_issue(url: str) -> str | ErrorResponse:
    """Fetch a GitHub Issue or Pull Request with all comments as structured Markdown.

    Parses the URL, fetches the full issue/PR thread via ``gh`` CLI, and renders
    all comments sorted by reactions with author/date/reactions metadata.

    Args:
        url: Full GitHub issue or PR URL
             (e.g. https://github.com/owner/repo/issues/123)

    Returns:
        str: Markdown-formatted issue/PR thread with all comments.

    Examples:
        - https://github.com/astral-sh/uv/issues/1
        - https://github.com/python/cpython/pull/100000

    Error Handling:
        - Invalid URL: Returns error message
        - gh CLI not installed or authenticated: Returns error with instructions
        - Timeout or API error: Returns error message

    """
    try:
        return _get_github_issue(url)
    except Exception as e:
        logger.exception("get_github_issue failed")
        return format_error(f"Failed to fetch issue: {e}")


# ─────────────────────────────────────────────────────────────
# X/Twitter tools — requires AUTH_TOKEN + CT0 cookies
# Best for: real-time discourse, breaking news, community signal
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_x",
    annotations={
        "title": "Search X/Twitter via Bird CLI",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_x(
    query: str,
    from_date: str | None = None,
    max_results: int = 30,
    depth: Depth = "default",
    response_format: ResponseFormat = "markdown",
) -> str | list[dict[str, Any]] | ErrorResponse:
    """Search X/Twitter via Bird CLI — requires AUTH_TOKEN and CT0 cookies.

    Role: Real-time discourse. Use this for breaking news, community
    reactions, and engagement signals from X/Twitter.

    Authentication: Set AUTH_TOKEN and CT0 environment variables. Extract
    these from your browser cookies after logging in to x.com. These are
    session cookies that expire periodically.

    Args:
        query: Search query string
        from_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        max_results: Max results (capped by depth: quick=12, default=30, deep=60)
        depth: Search depth — 'quick', 'default', or 'deep'
        response_format: Output format ('json' or 'markdown')

    Returns:
        str: Markdown-formatted results (when response_format="markdown")
        list: Tweets with text, url, author_handle, date, and engagement metrics
        ErrorResponse: Error response if applicable

    Examples:
        - "Claude Code" — find recent posts about Claude Code
        - "OpenAI news" — find breaking news about OpenAI
        - "from:sama" — search posts from a specific user

    Error Handling:
        - Missing credentials: Set AUTH_TOKEN and CT0 env vars.
        - Node.js missing: Install Node.js 22+ for the vendored Bird CLI.

    """
    try:
        items = _search_x(query=query, from_date=from_date, depth=depth)[:max_results]
        if response_format == "markdown":
            return _format_x_markdown(items, query)
        return cast("list[dict]", items)
    except Exception as e:
        logger.exception("X search failed")
        return format_error(f"X search failed: {e}")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
