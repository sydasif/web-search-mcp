import logging
from typing import Literal

from fastmcp import FastMCP

from .compare import compare_tech as _compare_tech
from .ddg import ddg_search, format_search_results_markdown
from .ddg import fetch_page as _fetch_page
from .errors import translate_error as _translate_error
from .github import get_github_issue as _get_github_issue
from .groq_tools import (
    analyze_page as _groq_analyze_page,
    search as _groq_search,
)
from .hackernews import enrich_top_stories as _enrich_hn
from .hackernews import search_hackernews as _search_hn
from .models import ErrorResponse, FetchOutputFormat, PageResponse, SearchRequest, SearchResponse
from .polymarket import search_polymarket as _search_pm
from .reddit import reddit_search_tool as _reddit_search_tool
from .registries import (
    format_package_info as _fmt_pkg_info,
)
from .registries import (
    format_package_list as _fmt_pkg_list,
)
from .registries import (
    lookup_package as _lookup_package,
)
from .registries import (
    search_packages as _search_packages,
)
from .utils import format_error, format_results_markdown
from .wikipedia import wikipedia_search_tool as _wikipedia_search_tool
from .x import search_x as _search_x

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
    domain: str | None = None,
) -> str | SearchResponse | ErrorResponse:
    """Search the web via DuckDuckGo — free, fast, returns raw structured results.

    Role: Discovery. Use this as your first-pass search for broad coverage.
    Workflow: Feed results into groq_search for deep validation, or
    fetch_page to get full page content. Alternative: groq_search
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
        logger.error("Search failed: %s", e)
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

    Returns:
        PageResponse: Extracted content and metadata
        ErrorResponse: Error response if applicable

    Examples:
        - "https://docs.python.org/3/library/os.html"
        - "https://www.nature.com/articles/s41586-024-00000-0"

    Error Handling:
        - HTTP 403 Forbidden: The site is blocking the request. Try changing the backend to 'curl'.
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
        backend=backend,
    )


# ─────────────────────────────────────────────────────────────
# Reddit tools — keyless, free Reddit search
# Best for: community discussions, opinions, real user experiences
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="reddit_search",
    annotations={
        "title": "Search Reddit via keyless RSS + shreddit enrichment",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def reddit_search(
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
    community insights. Alternative: web_search for general web results,
    groq_search for synthesized multi-source research.

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
    name="hackernews_search",
    annotations={
        "title": "Search Hacker News via Algolia API",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def hackernews_search(
    query: str,
    max_results: int = 30,
    depth: Literal["quick", "default", "deep"] = "default",
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
    """Search Hacker News via Algolia API — free, no API key needed.

    Role: Tech discourse. Use this for developer news, startup discussions,
    and technical opinions. Alternative: web_search for general results,
    groq_search for synthesized multi-source research.

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
    try:
        items = _search_hn(query, depth=depth)[:max_results]
        items = _enrich_hn(items, depth=depth)
        if response_format == "markdown":
            return _format_hn_markdown(items, query)
        return items
    except Exception as e:
        logger.error("Hacker News search failed: %s", e)
        return format_error(f"Hacker News search failed: {e}")


def _format_hn_markdown(items: list[dict], query: str) -> str:
    """Format HN results as markdown."""
    def _item_lines(item: dict, i: int) -> list[str]:
        points = item.get("engagement", {}).get("points", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        hn_url = item.get("hn_url", item.get("url", "#"))
        lines = [
            f"{i}. **[{item.get('title', 'Untitled')}]({hn_url})**",
            f"   {points} points, {comments} comments | {item.get('date', '')}",
        ]
        if item.get("top_comments"):
            lines.append("   Top comments:")
            for c in item["top_comments"][:2]:
                lines.append(f"   > {c.get('text', '')[:200]}...")
        return lines
    return format_results_markdown(items, query, "Hacker News", "stories", _item_lines)


# ─────────────────────────────────────────────────────────────
# Polymarket tools — free, prediction markets
# Best for: odds, predictions, market signals
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="polymarket_search",
    annotations={
        "title": "Search Polymarket prediction markets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def polymarket_search(
    topic: str,
    max_results: int = 15,
    depth: Literal["quick", "default", "deep"] = "default",
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
    """Search Polymarket prediction markets via Gamma API — free, no API key needed.

    Role: Prediction signals. Use this for odds, market movements, and
    crowd-sourced probability estimates. Alternative: web_search for
    general news, groq_search for synthesized multi-source research.

    Args:
        topic: Search topic (e.g. 'NVIDIA', 'presidential election', 'Fed rate cut')
        max_results: Max results (capped by depth: quick=5, default=15, deep=25)
        depth: Search depth — controls query expansion and result limits
        response_format: Output format ('json' or 'markdown')

    Returns:
        list: Polymarket events with outcome prices, volume, and liquidity
        str: Markdown-formatted results (when response_format="markdown")

    Examples:
        - "Will the Fed cut rates in 2026"
        - "NVIDIA stock price"
        - "US presidential election"

    Error Handling:
        - Empty results: Try a broader topic or different phrasing.
    """
    try:
        items = _search_pm(topic, depth=depth)[:max_results]
        if response_format == "markdown":
            return _format_pm_markdown(items, topic)
        return items
    except Exception as e:
        logger.error("Polymarket search failed: %s", e)
        return format_error(f"Polymarket search failed: {e}")


def _format_pm_markdown(items: list[dict], topic: str) -> str:
    """Format Polymarket results as markdown."""
    def _item_lines(item: dict, i: int) -> list[str]:
        lines = [f"{i}. **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**"]
        outcomes = item.get("outcome_prices", [])
        if outcomes:
            odds_str = ", ".join(f"{name}: {p:.0%}" for name, p in outcomes)
            lines.append(f"   Odds: {odds_str}")
        vol = item.get("volume1mo") or item.get("volume24hr") or 0
        if vol:
            lines.append(f"   Volume: ${vol:,.0f}")
        if item.get("price_movement"):
            lines.append(f"   Movement: {item['price_movement']}")
        return lines
    return format_results_markdown(items, topic, "Polymarket", "markets", _item_lines)


# ─────────────────────────────────────────────────────────────
# Wikipedia tools — free, open encyclopedia
# Best for: factual summaries, background research, citations
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="wikipedia_search",
    annotations={
        "title": "Search Wikipedia and read articles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def wikipedia_search(
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
        logger.error("Wikipedia search failed: %s", e)
        return format_error(f"Wikipedia search failed: {e}")


# ─────────────────────────────────────────────────────────────
# GitHub tools — issues/PRs search, auth via GITHUB_TOKEN or gh
# Best for: code discussions, bug reports, feature requests
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="github_search",
    annotations={
        "title": "Search GitHub Issues and PRs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def github_search(
    query: str,
    max_results: int = 30,
    depth: Literal["quick", "default", "deep"] = "default",
    token: str | None = None,
    response_format: Literal["json", "markdown"] = "markdown",
) -> str | list[dict] | ErrorResponse:
    """Search GitHub Issues and PRs via the GitHub Search API.

    Role: Code & issues. Use this for bug discussions, feature requests,
    and community sentiment on GitHub projects. Alternative: web_search
    for general results, or web_search with domain="docs.python.org" for documentation.

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
    try:
        from .github import enrich_with_comments as _enrich_gh
        from .github import search_github as _search_gh

        items = _search_gh(query, depth=depth, token=token)[:max_results]
        items = _enrich_gh(items, depth=depth, token=token)
        if response_format == "markdown":
            return _format_gh_markdown(items, query)
        return items
    except Exception as e:
        logger.error("GitHub search failed: %s", e)
        return format_error(f"GitHub search failed: {e}")


def _format_gh_markdown(items: list[dict], query: str) -> str:
    """Format GitHub results as markdown."""
    def _item_lines(item: dict, i: int) -> list[str]:
        emoji = "🔀" if item.get("is_pr") else "🐛"
        repo = item.get("repository", "")
        reactions = item.get("engagement", {}).get("reactions", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        lines = [
            f"{i}. {emoji} **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**",
            f"   {repo} | {item.get('author', '')} | {item.get('date', '')}",
            f"   ❤️ {reactions} reactions, 💬 {comments} comments",
        ]
        labels = item.get("labels", [])
        if labels:
            lines.append(f"   Labels: {', '.join(labels[:5])}")
        if item.get("top_comments"):
            lines.append("   Top comment:")
            for c in item["top_comments"][:1]:
                lines.append(f"   > {c.get('excerpt', '')[:200]}...")
        return lines
    return format_results_markdown(items, query, "GitHub", "issues/PRs", _item_lines)


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
        logger.error("get_github_issue failed: %s", e)
        return format_error(f"Failed to fetch issue: {e}")# ─────────────────────────────────────────────────────────────
# Groq tools — AI-powered web search (browse + compound)
# Best for: deep research, validation, multi-step synthesis
# Costs tokens — use DDG tools for quick lookups
# ─────────────────────────────────────────────────────────────

@mcp.tool(
    name="groq_search",
    annotations={
        "title": "AI-powered web search via Groq",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def groq_search(
    query: str,
    model: Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b", "groq/compound", "groq/compound-mini"] = "groq/compound-mini",
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

    Args:
        query: Search question or topic
        model: Which Groq model to use:
            - 'groq/compound-mini' (default): Fast auto-research, 1 tool call
            - 'groq/compound': Deep auto-research, up to 10 tool calls
            - 'openai/gpt-oss-20b': Interactive browsing (fast)
            - 'openai/gpt-oss-120b': Interactive browsing (thorough)
        reasoning_effort: Reasoning intensity for GPT-OSS models ('low', 'medium', 'high').
            'low' balances quality vs token cost; 'high' explores more pages.

    Returns:
        str: Synthesized research results from multiple web sources
        ErrorResponse: Error response if applicable

    Examples:
        - "Analyze the current state of quantum computing breakthroughs in 2026"
        - "Find the latest pricing for NVIDIA H200 across three different vendors"
        - "Compare the performance of React vs Vue in 2026"

    Error Handling:
        - API Key Missing: Ensure GROQ_API_KEY is set in your environment.
        - Rate Limit: Groq API limit reached. Wait a few minutes before retrying.
        - Request too long: Keep your query under 150 characters.
    """
    return _groq_search(query=query, model=model, reasoning_effort=reasoning_effort)


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
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound-mini",
) -> str | ErrorResponse:
    """Visit and analyze a URL via Groq Compound — fetches and interprets content.

    Role: Interpretation. Use this AFTER fetch_page when you need AI analysis
    of the content (e.g. "Find the argument for X", "Extract the data table").
    Alternative: fetch_page gives you raw content for free — use that when
    you just need to read the text yourself.

    Note: Large pages may hit Groq's internal request-body limit. If so,
    use fetch_page first, then ask a specific question about the content.

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
    return _groq_analyze_page(url=url, query=query, model=model)


# ─────────────────────────────────────────────────────────────
# X/Twitter tools — requires AUTH_TOKEN + CT0 cookies
# Best for: real-time discourse, breaking news, community signal
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="x_search",
    annotations={
        "title": "Search X/Twitter via Bird CLI",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def x_search(
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
        logger.error("X search failed: %s", e)
        return format_error(f"X search failed: {e}")


def _format_x_markdown(items: list[dict], query: str) -> str:
    """Format X results as markdown."""
    # Check for auth errors (unique to X tool)
    if len(items) == 1 and "error" in items[0]:
        return f"⚠️ {items[0]['error']}"

    def _item_lines(item: dict, i: int) -> list[str]:
        handle = item.get("author_handle", "unknown")
        url = item.get("url", "#")
        text = (item.get("text", "") or "")[:200]
        lines = [
            f"{i}. **@{handle}** · [{url}]({url})",
            f"   {text}{'...' if len(item.get('text', '') or '') > 200 else ''}",
        ]
        eng = item.get("engagement", {}) or {}
        eng_parts = []
        if eng.get("likes"):
            eng_parts.append(f"❤️ {eng['likes']}")
        if eng.get("retweets"):
            eng_parts.append(f"🔁 {eng['retweets']}")
        if eng.get("replies"):
            eng_parts.append(f"💬 {eng['replies']}")
        if eng_parts:
            lines.append(f"   {' '.join(eng_parts)}")
        if item.get("date"):
            lines.append(f"   {item['date']}")
        return lines
    return format_results_markdown(items, query, "X/Twitter", "posts", _item_lines)


# ─────────────────────────────────────────────────────────────
# Developer tools — package registries, error translation, comparisons
# Best for: developer workflows, debugging, technology evaluation
# ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="package_info",
    annotations={
        "title": "Look up a package from npm, PyPI, crates.io, or Go modules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def package_info(
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
        logger.error("package_info failed: %s", e)
        return format_error(f"Package lookup failed for '{name}'", str(e))


@mcp.tool(
    name="package_search",
    annotations={
        "title": "Search packages by keyword on npm, PyPI, crates.io, or Go",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def package_search(
    query: str,
    registry: Literal["npm", "pypi", "crates", "go"] = "npm",
    max_results: int = 5,
) -> str | ErrorResponse:
    """Search for packages by keyword across a package registry.

    Role: Developer tooling. Use this to discover packages related to a
    topic. Follow up with ``package_info`` for detailed metadata.

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
        logger.error("package_search failed: %s", e)
        return format_error(f"Package search failed for '{query}'", str(e))


@mcp.tool(
    name="translate_error",
    annotations={
        "title": "Analyze error messages and find solutions from Stack Overflow",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def translate_error(
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
        logger.error("translate_error failed: %s", e)
        return format_error("Error analysis failed", str(e))


@mcp.tool(
    name="compare_tech",
    annotations={
        "title": "Compare two technologies side-by-side",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def compare_tech(
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
        logger.error("compare_tech failed: %s", e)
        return format_error("Comparison failed", str(e))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
