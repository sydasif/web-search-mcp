import logging
from typing import Literal

from fastmcp import FastMCP

from .models import SearchRequest, FetchOutputFormat, SearchResponse, PageResponse, ErrorResponse
from .search import ddg_search, format_search_results_markdown
from .utils import format_error
from .reader import fetch_page as _fetch_page
from .research import search_domain as _search_domain

# Set up logging
logger = logging.getLogger("web-search-mcp")

mcp = FastMCP("Web Search Tools")


@mcp.tool(
    name="web_search",
    annotations={
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
    """
    Unified search tool for web content and news.

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
        return result if result is not None else format_error("No results returned from search")
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return format_error("Search failed", str(e))


@mcp.tool(
    name="fetch_page",
    annotations={
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
    """
    Extracts the full text content from a web page URL.
    Use this to read the details of a specific result found via web_search.

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
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def search_docs(query: str, domain: str = "docs.python.org") -> SearchResponse | ErrorResponse:
    """
    Searches specifically for technical documentation or content on a specific domain.

    Args:
        query: What you're looking for
        domain: The domain to search (e.g. 'docs.python.org', 'stackoverflow.com')

    Returns:
        Search results from the specified domain
    """
    return _search_domain(query, domain=domain)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
