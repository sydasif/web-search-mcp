import logging
from typing import Literal

from fastmcp import FastMCP

from ._models import ErrorResponse, FetchOutputFormat, PageResponse, SearchRequest, SearchResponse
from ._utils import format_error
from .search.ddg import ddg_search, format_search_results_markdown
from .search.ddg import fetch_page as _fetch_page
from .search.exa import exa_search as _exa_search
from .search.exa import exa_search_advanced as _exa_search_advanced
from .search.exa import format_exa_markdown as _format_exa_markdown
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
from .tools.arxiv import arxiv_search_tool as _arxiv_search_tool
from .tools.compare import compare_tech as _compare_tech
from .tools.errors import translate_error as _translate_error
from .tools.groq_tools import groq_analyze as _groq_analyze
from .tools.groq_tools import search as _groq_search
from .tools.registries import (
    format_package_info as _fmt_pkg_info,
)
from .tools.registries import (
    format_package_list as _fmt_pkg_list,
)
from .tools.registries import (
    lookup_package as _lookup_package,
)
from .tools.registries import (
    search_packages as _search_packages,
)
from .tools.wikipedia import wikipedia_search_tool as _wikipedia_search_tool

# Set up logging
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
        "title": "Search the web via DuckDuckGo",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_web(
    query: str,
    search_type: Literal["text", "news"] = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: Literal["moderate", "off", "on"] = "moderate",
    page: int = 1,
    backend: Literal["auto", "legacy", "api"] = "auto",
    response_format: Literal["json", "markdown"] = "markdown",
    domain: str | None = None,
) -> str | SearchResponse | ErrorResponse:
    """Search the web via DuckDuckGo — free, fast, returns raw structured results.

    Role: Discovery. Use this as your first-pass search for broad coverage.
    Workflow: Feed results into fetch_web_page to get full page content or
    groq_analyze for AI-powered page analysis.

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
        domain: Optional domain to scope results (e.g. 'docs.python.org').
            Automatically adds a site: prefix. Use for targeted documentation searches.

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
            safesearch=safesearch,
            page=page,
            backend=backend,
            response_format=response_format,
        )
        result = ddg_search(req)
        if response_format == "markdown":
            return format_search_results_markdown(result)
        return result
    except Exception as e:
        logger.exception("Search failed")
        return format_error(
            "DuckDuckGo search failed",
            f"{e}. Try reducing max_results, switching search_type, or using a more specific query.",
        )


@mcp.tool(
    name="fetch_web_page",
    annotations={
        "title": "Extract text content from a URL",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def fetch_web_page(
    url: str,
    output_format: FetchOutputFormat = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> PageResponse | ErrorResponse:
    """Extract raw text content from a URL — fast, free, full control.

    Role: Retrieval. Use this when you need the actual page content (not a
    summary). Supports bot-detection bypass and multiple output formats.
    Workflow: Pipe the content into groq_analyze for AI interpretation.
    Alternative: groq_analyze fetches AND interprets in one step, but
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

    Returns:
        PageResponse: Extracted content and metadata
        ErrorResponse: Error response if applicable

    Examples:
        - "https://docs.python.org/3/library/os.html"
        - "https://www.nature.com/articles/s41586-024-00000-0"

    Error Handling:
        - HTTP 403 Forbidden: The site is blocking the request. The server automatically falls back to Exa.
        - Timeout: The page is taking too long to respond. Increase the timeout parameter.

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
    search_type: Literal["text", "news"] = "text",
    max_results: int = 25,
    time_range: str | None = None,
    depth: Literal["quick", "default", "deep"] = "default",
    subreddits: list[str] | None = None,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Reddit via keyless RSS + shreddit enrichment — free, no API key needed.

    Role: Discovery. Use this for Reddit-specific discussions, opinions, and
    community insights.    Alternative: search_web for general web results.

    Workflow: Three-tier keyless pipeline:
    - Tier 0: Legacy .json search (often 403, tried once)
    - Tier 1: RSS discovery (load-bearing, robust)
    - Tier 2: Shreddit comment enrichment for top posts

    Args:
        query: Search query string
        search_type: Type of search (only 'text' supported for Reddit)
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
        - Reddit 403/429: The free keyless path is rate-limited. Try a different query, target specific subreddits, or wait.

    """
    return _reddit_search_tool(
        query=query,
        search_type=search_type,
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
    depth: Literal["quick", "default", "deep"] = "default",
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
    """Search Hacker News via Algolia API — free, no API key needed.

    Role: Tech discourse. Use this for developer news, startup discussions,
    and technical opinions. Alternative: search_web for general results.

    Args:
        query: Search query string
        max_results: Max results (capped by depth: quick=15, default=30, deep=60)
        depth: Search depth — controls result limits and comment enrichment
        response_format: Output format ('json' or 'markdown')

    Returns:
        list: Hacker News stories with engagement scores and optional comments
        str: Markdown-formatted results (when response_format="markdown")

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
    sort_by: Literal["relevance", "submitted_date", "updated_date"] = "relevance",
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
    depth: Literal["quick", "default", "deep"] = "default",
    token: str | None = None,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
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
        list: GitHub issues/PRs with reactions, labels, and optional comments
        str: Markdown-formatted results (when response_format="markdown")

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


@mcp.tool(
    name="groq_search",
    annotations={
        "title": "Interactive web browsing via Groq GPT-OSS models",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_search(
    query: str,
    model: Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"] = "openai/gpt-oss-20b",
    reasoning_effort: Literal["low", "medium", "high"] = "low",
) -> str | ErrorResponse:
    """Interactive web browsing via GPT-OSS models — explores pages step by step.

    Role: Interactive browsing. Use when you need the model to navigate through
    documentation, click through multi-step guides, or handle JS-rendered pages.
    The model actively browses pages and synthesizes what it finds.

    Alternative: search_web for raw DDG results (free, no tokens), or
    groq_analyze for analyzing a specific URL via Compound.

    Note: GPT-OSS models use explicit ``browser_search`` tool configuration.
    Long queries may hit Groq's payload size limit (413 error). If this happens,
    shorten your query or split it into smaller parts.

    Args:
        query: Search question or browsing task
        model: GPT-OSS model to use:
            - 'openai/gpt-oss-20b' (default): Faster, lighter browsing
            - 'openai/gpt-oss-120b': More thorough, handles complex tasks
        reasoning_effort: Reasoning intensity ('low', 'medium', 'high').
            'low' balances speed vs depth; 'high' explores more.

    Returns:
        str: Synthesized research results from browsing
        ErrorResponse: Error response if applicable

    Examples:
        - "Walk through the uv setup guide on docs.astral.sh"
        - "Find the latest pricing for NVIDIA H200 across three vendors"
        - "Compare React vs Vue features from their official docs"

    Error Handling:
        - API Key Missing: Ensure GROQ_API_KEY is set in your environment.
        - Request too large: Keep your query under ~100 characters or split it.

    """
    return _groq_search(query=query, model=model, reasoning_effort=reasoning_effort)


@mcp.tool(
    name="groq_analyze",
    annotations={
        "title": "Analyze a web page via Groq Compound",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_analyze(
    url: str,
    query: str = "Summarize the key points of this page.",
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound-mini",
) -> str | ErrorResponse:
    """Visit and analyze a URL via Groq Compound — fetches and interprets content.

    Role: Interpretation. Use this AFTER fetch_web_page when you need AI analysis
    of the content (e.g. "Find the argument for X", "Extract the data table").
    Alternative: fetch_web_page gives you raw content for free — use that when
    you just need to read the text yourself.

    Note: Large pages may hit Groq's internal request-body limit. If so,
    use fetch_web_page first, then ask a specific question about the content.

    Args:
        url: The URL to visit and analyze
        query: What to do with the page content (default: summarize key points)
        model: Compound system to use. 'groq/compound-mini' (default) is more
               reliable; 'groq/compound' may hit request-body limits on large pages.

    Returns:
        str: AI analysis based on the visited page content
        ErrorResponse: Error response if applicable

    Examples:
        - url="https://openai.com/blog/sora", query="What are the key limitations of Sora?"
        - url="https://arxiv.org/pdf/2401.00000.pdf", query="Extract the main findings of the results section"

    Error Handling:
        - Page too large: The content exceeds Groq's context window. Use fetch_page first.
        - Access Denied: The page is behind a paywall or blocking the analyzer.

    """
    return _groq_analyze(url=url, query=query, model=model)


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
    depth: Literal["quick", "default", "deep"] = "default",
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
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
        list: Tweets with text, url, author_handle, date, and engagement metrics
        str: Markdown-formatted results (when response_format="markdown")

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
        return items
    except Exception as e:
        logger.exception("X search failed")
        return format_error(f"X search failed: {e}")


# ─────────────────────────────────────────────────────────────
# Developer tools — package registries, error translation, comparisons
# Best for: developer workflows, debugging, technology evaluation
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="get_package_info",
    annotations={
        "title": "Look up a package from npm, PyPI, crates.io, or Go modules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def get_package_info(
    name: str,
    registry: Literal["npm", "pypi", "crates", "go"] | None = None,
) -> str | ErrorResponse:
    """Look up a specific package from npm, PyPI, crates.io, or Go modules.

    Role: Developer tooling. Use this to get version, description, downloads,
    license, dependencies count, and repository info for any package.

    Args:
        name: Package name (e.g. ``"express"``, ``"numpy"``, ``"serde"``).
            Auto-detects registry from the name format.
        registry: Force a specific registry (``"npm"``, ``"pypi"``,
            ``"crates"``, ``"go"``). Auto-detected if omitted.

    Returns:
        Markdown-formatted package metadata.

    Examples:
        - ``"requests"`` → PyPI lookup (auto-detected)
        - ``"express"`` → npm lookup (auto-detected)
        - ``"serde"`` → crates.io lookup (explicit registry)

    Error Handling:
        - Package not found: Returns clear message with registry info.
        - Registry down: Returns error message.

    """
    try:
        result = _lookup_package(name, registry=registry)
        if isinstance(result, ErrorResponse):
            return result
        return _fmt_pkg_info(result)
    except Exception as e:
        logger.exception("package_info failed")
        return format_error(f"Package lookup failed for '{name}'", str(e))


@mcp.tool(
    name="search_packages",
    annotations={
        "title": "Search packages by keyword on npm, PyPI, crates.io, or Go",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_packages(
    query: str,
    registry: Literal["npm", "pypi", "crates", "go"] = "npm",
    max_results: int = 5,
) -> str | ErrorResponse:
    """Search for packages by keyword across a package registry.

    Role: Developer tooling. Use this to discover packages related to a
    topic. Follow up with ``get_package_info`` for detailed metadata.

    Args:
        query: Search keywords (e.g. ``"async http client"``).
        registry: Registry to search (``"npm"``, ``"pypi"``,
            ``"crates"``, ``"go"``). Defaults to ``"npm"``.
        max_results: Max results (1-20).

    Returns:
        Markdown-formatted list of matching packages.

    Examples:
        - ``"async http client"`` on npm
        - ``"dataframe"`` on PyPI
        - ``"serialization"`` on crates.io

    Error Handling:
        - Empty query: Returns error message.
        - No results: Returns "No packages found" message.

    """
    try:
        result = _search_packages(query, registry=registry, max_results=max_results)
        if isinstance(result, ErrorResponse):
            return result
        return _fmt_pkg_list(result, query, registry)
    except Exception as e:
        logger.exception("package_search failed")
        return format_error(f"Package search failed for '{query}'", str(e))


@mcp.tool(
    name="analyze_error",
    annotations={
        "title": "Analyze error messages and find solutions from Stack Overflow",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def analyze_error(
    error_message: str,
    max_results: int = 5,
    language: str | None = None,
) -> str | ErrorResponse:
    """Parse an error message and search Stack Overflow for solutions.

    Role: Developer tooling. Use this when you get an error in your code
    and want to understand what caused it and how to fix it. The tool
    auto-detects the programming language and framework from the error.

    Args:
        error_message: The full error message or stack trace. Pass the
            entire error - the parser extracts the relevant parts.
        max_results: Number of Stack Overflow results to return (1-10).
        language: Optionally specify the language (``"python"``,
            ``"javascript"``, ``"typescript"``, ``"rust"``, ``"go"``,
            ``"java"``). Auto-detected if omitted.

    Returns:
        Markdown with parsed error analysis and Stack Overflow solutions.

    Examples:
        - Python traceback with ``AttributeError``
        - Node.js ``Cannot read property`` error
        - Rust borrow checker error E0502

    Error Handling:
        - Empty input: Returns error message.
        - No Stack Overflow results: Returns partial analysis with note.

    """
    try:
        return _translate_error(error_message, max_results=max_results, language=language)
    except Exception as e:
        logger.exception("translate_error failed")
        return format_error("Error analysis failed", str(e))


@mcp.tool(
    name="compare_technologies",
    annotations={
        "title": "Compare two technologies side-by-side",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def compare_technologies(
    tech_a: str,
    tech_b: str,
    category: Literal["framework", "library", "database", "language", "tool"] = "library",
) -> str | ErrorResponse:
    """Compare two technologies side-by-side using GitHub and registry data.

    Role: Developer tooling. Use this to evaluate technology choices with
    real data: GitHub stars, download counts, version info, and license.

    Args:
        tech_a: First technology name (e.g. ``"React"``).
        tech_b: Second technology name (e.g. ``"Vue"``).
        category: Category hint (``"framework"``, ``"library"``,
            ``"database"``, ``"language"``, ``"tool"``).

    Returns:
        Markdown table with side-by-side comparison and detail sections.

    Examples:
        - compare_tech("React", "Vue", category="framework")
        - compare_tech("Django", "FastAPI", category="framework")
        - compare_tech("PostgreSQL", "MongoDB", category="database")

    Error Handling:
        - Unknown technology: Returns partial data for found items.
        - GitHub API rate limited: Returns what data is available.

    """
    try:
        return _compare_tech(tech_a, tech_b, category=category)
    except Exception as e:
        logger.exception("compare_tech failed")
        return format_error("Comparison failed", str(e))


# ─────────────────────────────────────────────────────────────
# Exa AI tools — semantic search, free, no API key
# Best for: semantic discovery, filtered search, JS-heavy pages
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="search_exa",
    annotations={
        "title": "Semantic web search via Exa AI",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_exa(
    query: str,
    max_results: int = 5,
    category: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search_type: str | None = None,
    contents_text: bool = False,
    contents_highlights: bool = False,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
    """Semantic web search via Exa AI. Optional EXA_API_KEY increases rate limits.

    Role: Semantic discovery. Use when keyword search gives poor results
    or you need AI-understood relevance. Exa uses semantic matching instead
    of keyword matching.

    Args:
        query: Natural language query (Exa works best with full sentences)
        max_results: Max results (default 5)
        category: Content type filter ('company', 'research paper', 'news', 'tweet')
        include_domains: Only search these domains (e.g. ['github.com'])
        exclude_domains: Exclude these domains
        start_date: Only results after this date (YYYY-MM-DD)
        end_date: Only results before this date (YYYY-MM-DD)
        search_type: Search mode ('auto', 'instant', 'fast', 'deep-lite', 'deep', 'deep-reasoning')
        contents_text: Include full page text in results
        contents_highlights: Include highlighted snippets in results
        response_format: 'json' for structured data, 'markdown' for readable

    Returns:
        list: Results with title, url, snippet
        str: Markdown-formatted results

    Examples:
        - "What are the best Python async frameworks in 2026"
        - query="Claude code review", include_domains=["reddit.com"]
        - query="AI regulation news", category="news", start_date="2026-01-01"
        - query="compare Rust vs Go", search_type="deep"

    Error Handling:
        - Empty results: Try a more general query or remove domain filters.
        - Rate limit: Exa free tier is 20K req/month. Wait if exhausted.
    """
    try:
        has_filters = any([category, include_domains, exclude_domains, start_date, end_date])
        use_advanced = has_filters or search_type or contents_text or contents_highlights
        if use_advanced:
            contents = {}
            if contents_text:
                contents["text"] = True
            if contents_highlights:
                contents["highlights"] = True
            data = _exa_search_advanced(
                query,
                num_results=max_results,
                category=category,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                start_date=start_date,
                end_date=end_date,
                search_type=search_type,
                contents=contents if contents else None,
            )
            if not data:
                return format_error("Exa search returned no results")
            results = data.get("results", []) if isinstance(data, dict) else []
            if response_format == "json":
                return results if results else []
            return _format_exa_markdown(results, query)

        items = _exa_search(query, num_results=max_results)
        if not items:
            return format_error("Exa search returned no results")
        if response_format == "json":
            return items

        return _format_exa_markdown(items, query)
    except Exception as e:
        logger.exception("Exa search failed")
        return format_error(f"Exa search failed: {e}")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
