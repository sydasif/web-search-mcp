import logging
from typing import Literal

from fastmcp import FastMCP

from .models import SearchRequest
from .search import ddg_search
from .weather import get_current_weather as weather_current
from .weather import get_forecast as weather_forecast
from .reader import fetch_page as _fetch_page
from .research import search_domain as _search_domain

# Set up logging
logger = logging.getLogger("web-search-mcp")

mcp = FastMCP("Web Search Tools")


@mcp.tool
def search_web(
    query: str,
    search_type: Literal["text", "news"] = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
) -> dict:
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

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
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
        )
        return ddg_search(req)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": "Search failed", "details": str(e)}


@mcp.tool
def get_weather(
    latitude: float,
    longitude: float,
    mode: Literal["current", "forecast"] = "forecast",
    days: int = 7,
) -> dict:
    """
    Get current weather or forecast for a specific location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        mode: Type of weather data ('current' or 'forecast', default 'forecast')
        days: Number of days for forecast (1-16, default 7, only used when mode='forecast')

    Returns:
        Dict containing weather data or error message
    """
    if mode == "current":
        return weather_current(latitude, longitude)
    else:
        return weather_forecast(latitude, longitude, days)


@mcp.tool
def fetch_page(
    url: str,
    output_format: Literal["text", "markdown", "json"] = "text",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> dict:
    """
    Extracts the full text content from a web page URL.
    Use this to read the details of a specific result found via search_web.

    Args:
        url: The URL to fetch and extract content from
        output_format: Format for extracted content ('text', 'markdown', 'json')
        include_metadata: Whether to include document metadata (title, author, date, etc.)
        include_tables: Whether to include table content in extraction
        include_comments: Whether to include comment content in extraction
        include_images: Whether to include image descriptions in extraction
        deduplicate: Whether to remove duplicated content
        max_length: Maximum length of content to return (default 15000)
        timeout: Request timeout in seconds (default 30)
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


@mcp.tool
def search_domain(query: str, domain: str = "docs.python.org") -> dict:
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
