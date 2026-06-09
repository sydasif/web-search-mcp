import logging
from typing import Literal

from fastmcp import FastMCP

from .models import SearchRequest, FetchOutputFormat, SearchResponse, PageResponse, ErrorResponse
from .ddg import ddg_search, format_search_results_markdown
from .utils import format_error
from .ddg import fetch_page as _fetch_page
from .groq_tools import (
    browse as _groq_browse,
    research as _groq_research,
    analyze_page as _groq_analyze_page,
)
from .reddit import reddit_search_tool as _reddit_search_tool
from .hackernews import search_hackernews as _search_hn, enrich_top_stories as _enrich_hn
from .polymarket import search_polymarket as _search_pm
from .x import search_x as _search_x  # noqa: F401 — used by x_search tool

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

    Examples:
        - "Latest NVIDIA H200 benchmarks"
        - "How to install uv on macOS"
        - "Current state of Llama 3.1 vs GPT-4o"

    Error Handling:
        - 429 Too Many Requests: Try reducing max_results or wait 60s.
        - Empty Results: Try a more general query or change search_type.
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
        SearchResponse: Search results from the specified domain
        ErrorResponse: Error response if applicable

    Examples:
        - query="asyncio event loop", domain="docs.python.org"
        - query="useEffect cleanup", domain="react.dev"

    Error Handling:
        - Empty results: Try a more general query or verify the domain is correct.
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
        logger.error("Domain search failed for query %r on domain %r: %s", query, domain, e)
        return format_error("Search failed", str(e))


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
    groq_research for synthesized multi-source research.

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
    groq_research for synthesized multi-source research.

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
    if not items:
        return f"No Hacker News results found for '{query}'."
    lines = [f"# Hacker News Results for '{query}'", f"Found {len(items)} stories.", ""]
    for i, item in enumerate(items, 1):
        points = item.get("engagement", {}).get("points", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        hn_url = item.get("hn_url", item.get("url", "#"))
        lines.append(f"{i}. **[{item.get('title', 'Untitled')}]({hn_url})**")
        lines.append(f"   {points} points, {comments} comments | {item.get('date', '')}")
        if item.get("top_comments"):
            lines.append("   Top comments:")
            for c in item["top_comments"][:2]:
                lines.append(f"   > {c.get('text', '')[:200]}...")
        lines.append("")
    return "\n".join(lines)


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
    general news, groq_research for synthesized multi-source research.

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
    if not items:
        return f"No Polymarket results found for '{topic}'."
    lines = [f"# Polymarket Results for '{topic}'", f"Found {len(items)} markets.", ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**")
        outcomes = item.get("outcome_prices", [])
        if outcomes:
            odds_str = ", ".join(f"{name}: {p:.0%}" for name, p in outcomes)
            lines.append(f"   Odds: {odds_str}")
        vol = item.get("volume1mo") or item.get("volume24hr") or 0
        if vol:
            lines.append(f"   Volume: ${vol:,.0f}")
        if item.get("price_movement"):
            lines.append(f"   Movement: {item['price_movement']}")
        lines.append("")
    return "\n".join(lines)


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
    for general results, search_docs for documentation.

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
        from .github import search_github as _search_gh
        from .github import enrich_with_comments as _enrich_gh

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
    if not items:
        return f"No GitHub results found for '{query}'."
    lines = [f"# GitHub Results for '{query}'", f"Found {len(items)} issues/PRs.", ""]
    for i, item in enumerate(items, 1):
        emoji = "🔀" if item.get("is_pr") else "🐛"
        repo = item.get("repository", "")
        lines.append(f"{i}. {emoji} **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**")
        lines.append(f"   {repo} | {item.get('author', '')} | {item.get('date', '')}")
        reactions = item.get("engagement", {}).get("reactions", 0)
        comments = item.get("engagement", {}).get("comments", 0)
        lines.append(f"   ❤️ {reactions} reactions, 💬 {comments} comments")
        labels = item.get("labels", [])
        if labels:
            lines.append(f"   Labels: {', '.join(labels[:5])}")
        if item.get("top_comments"):
            lines.append("   Top comment:")
            for c in item["top_comments"][:1]:
                lines.append(f"   > {c.get('excerpt', '')[:200]}...")
        lines.append("")
    return "\n".join(lines)


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
    """Interactive browser search via Groq — navigates pages like a human.

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
        str: Combined results from multiple web sources
        ErrorResponse: Error response if applicable

    Examples:
        - "Compare the performance of React vs Vue in 2026, focusing on hydration patterns"
        - "Find the latest pricing for NVIDIA H200 across three different vendors"

    Error Handling:
        - API Key Missing: Ensure GROQ_API_KEY is set in your environment.
        - Rate Limit: Groq API limit reached. Wait a few minutes before retrying.
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
    model: Literal["groq/compound", "groq/compound-mini"] = "groq/compound-mini",
) -> str | ErrorResponse:
    """Deep research via Groq Compound — auto-selects search, browsing, and tools.

    Role: Validation & synthesis. Use this AFTER web_search to validate,
    deep-dive, or expand on initial results. Compound decides whether to
    search, visit pages, or use other tools to answer your question.
    Alternative: web_search for fast raw results, groq_browse for a
    simpler interactive browse.

    Note: Long queries may be truncated to fit Groq's internal search limit.
    Keep queries concise for best results.

    Args:
        query: Research question or topic for deep investigation
        model: Compound system to use. 'groq/compound-mini' (default) has ~3x
               lower latency but limits to 1 tool call; 'groq/compound' supports
               up to 10 tool calls.

    Returns:
        str: Synthesized research results from multiple sources
        ErrorResponse: Error response if applicable

    Examples:
        - "Analyze the current state of quantum computing breakthroughs in 2026"
        - "Investigation into the impact of Llama 3 on open-source software development"

    Error Handling:
        - Request too long: Keep your query under 150 characters.
        - Synthesis failure: The model could not find enough data to synthesize a result.
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
    if not items:
        return f"No X results found for '{query}'."
    # Check for auth errors
    if len(items) == 1 and "error" in items[0]:
        return f"⚠️ {items[0]['error']}"
    lines = [f"# X/Twitter Results for '{query}'", f"Found {len(items)} posts.", ""]
    for i, item in enumerate(items, 1):
        handle = item.get("author_handle", "unknown")
        url = item.get("url", "#")
        text = (item.get("text", "") or "")[:200]
        lines.append(f"{i}. **@{handle}** · [{url}]({url})")
        lines.append(f"   {text}{'...' if len(item.get('text', '') or '') > 200 else ''}")
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
        lines.append("")
    return "\n".join(lines)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
