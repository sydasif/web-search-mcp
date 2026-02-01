import logging
from typing import Literal

from fastmcp import FastMCP

from .models import SearchRequest
from .search import ddg_search
from .weather import get_current_weather as weather_current
from .weather import get_forecast as weather_forecast
from .reader import fetch_page as _fetch_page
from .research import search_docs as _search_docs

# Set up logging
logger = logging.getLogger("web-search-mcp")

mcp = FastMCP("Web Search Tools")


@mcp.tool
def search_web(
    query: str,
    search_type: Literal["text", "image", "images", "news", "video", "videos", "books"] = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
    # Image specific
    size: str | None = None,
    color: str | None = None,
    type_image: str | None = None,
    layout: str | None = None,
    license_image: str | None = None,
    # Video specific
    resolution: str | None = None,
    duration: str | None = None,
    license_videos: str | None = None,
    # Compatibility
    filters: dict | None = None,
) -> dict:
    """
    Unified search tool for web content, news, images, videos, and books.

    Args:
        query: Search query string
        search_type: Type of search ('text', 'image', 'news', 'video', 'books')
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')
        size: Image size filter ('Small', 'Medium', 'Large', 'Wallpaper')
        color: Image color filter
        type_image: Image type filter ('photo', 'clipart', 'gif', 'transparent', 'line')
        layout: Image layout filter ('Square', 'Tall', 'Wide')
        license_image: Image license filter
        resolution: Video resolution filter ('high', 'standart')
        duration: Video duration filter ('short', 'medium', 'long')
        license_videos: Video license filter ('creativeCommon', 'youtube')
        filters: Additional type-specific filters (backward compatibility)

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    if filters is None:
        filters = {}

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
            size=size,
            color=color,
            type_image=type_image,
            layout=layout,
            license_image=license_image,
            resolution=resolution,
            duration=duration,
            license_videos=license_videos,
            filters=filters,
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
def fetch_page(url: str) -> dict:
    """
    Extracts the full text content from a web page URL.
    Use this to read the details of a specific result found via search_web.
    """
    return _fetch_page(url)


@mcp.tool
def search_docs(query: str, tech_stack: str = "python") -> dict:
    """
    Searches specifically for technical documentation.

    Args:
        query: What you're looking for in the docs
        tech_stack: Which technology's docs to search (python, react, mcp)

    Returns:
        Search results from the specified documentation site
    """
    return _search_docs(query, tech_stack=tech_stack)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
