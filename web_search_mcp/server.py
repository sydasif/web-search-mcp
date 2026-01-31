import asyncio
import logging
import ssl
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP

from .config import settings
from .download import download_media
from .search import ddg_search
from .weather import get_current_weather as weather_current
from .weather import get_forecast as weather_forecast

# Global HTTP client for weather API
http_client = None
executor = ThreadPoolExecutor(max_workers=4)

# Set up logging
logger = logging.getLogger("web-search-mcp")


@asynccontextmanager
async def app_lifespan(app) -> AsyncIterator[None]:
    """Lifespan context manager to handle shared resources."""
    global http_client
    # Initialize shared resources
    ssl_context = (
        ssl.create_default_context()
        if hasattr(ssl, "create_default_context")
        else ssl._create_unverified_context()
    )
    http_client = httpx.AsyncClient(verify=ssl_context, timeout=30.0)
    logger.info("Shared HTTP client initialized")

    yield

    # Cleanup
    if http_client:
        await http_client.aclose()
    executor.shutdown(wait=True)
    logger.info("Shared HTTP client closed")


mcp = FastMCP("Web Search Tools", lifespan=app_lifespan)


async def _search_handler(search_type: str, query: str, **kwargs):
    """Centralized search handler to reduce code duplication."""
    try:
        return await ddg_search(query, search_type, **kwargs)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": "Search failed", "details": str(e)}


@mcp.tool
async def get_current_weather(latitude: float, longitude: float) -> dict:
    """
    Get current weather for a specific location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        Dict containing current weather data or error message
    """
    global http_client
    return await weather_current(latitude, longitude, http_client=http_client)


@mcp.tool
async def get_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    """
    Get daily weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        days: Number of days for forecast (1-16, default 7)

    Returns:
        Dict containing forecast data or error message
    """
    global http_client
    return await weather_forecast(latitude, longitude, days, http_client=http_client)


@mcp.tool
async def search_web(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
) -> dict:
    """
    Search for general web content using DuckDuckGo's text search.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return await _search_handler(
        "text",
        query,
        max_results=max_results,
        time_range=time_range,
        region=region,
        safesearch=safesearch,
        page=page,
        backend=backend,
    )


@mcp.tool
async def search_news(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
) -> dict:
    """
    Search for recent news and current events using DuckDuckGo's news search.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return await _search_handler(
        "news",
        query,
        max_results=max_results,
        time_range=time_range,
        region=region,
        safesearch=safesearch,
        page=page,
        backend=backend,
    )


@mcp.tool
async def search_images(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
    size: str | None = None,
    color: str | None = None,
    type_image: str | None = None,
    layout: str | None = None,
    license_image: str | None = None,
) -> dict:
    """
    Search for images including photos and visual content using DuckDuckGo's image search.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')
        size: Image size ('Small', 'Medium', 'Large', 'Wallpaper') or None
        color: Color filter (color name or 'Monochrome') or None
        type_image: Image type filter ('photo', 'clipart', 'gif', 'transparent', 'line') or None
        layout: Layout filter ('Square', 'Tall', 'Wide') or None
        license_image: License filter (Creative Commons types) or None

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return await _search_handler(
        "image",
        query,
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
    )


@mcp.tool
async def search_videos(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
    resolution: str | None = None,
    duration: str | None = None,
    license_videos: str | None = None,
) -> dict:
    """
    Search for videos including tutorials and multimedia content using DuckDuckGo's video search.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')
        resolution: Video resolution ('high', 'standart') or None
        duration: Video duration ('short', 'medium', 'long') or None
        license_videos: License filter ('creativeCommon', 'youtube') or None

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return await _search_handler(
        "video",
        query,
        max_results=max_results,
        time_range=time_range,
        region=region,
        safesearch=safesearch,
        page=page,
        backend=backend,
        resolution=resolution,
        duration=duration,
        license_videos=license_videos,
    )


@mcp.tool
async def search_books(
    query: str,
    max_results: int = 5,
    page: int = 1,
    backend: str = "auto",
) -> dict:
    """
    Search for books using DuckDuckGo's books search.

    Args:
        query: Search query string
        max_results: Max number of results to return (default 5)
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return await _search_handler(
        "books", query, max_results=max_results, page=page, backend=backend
    )


@mcp.tool
async def download_video(url: str, path: str | None = None, timeout: int = 30) -> dict:
    """
    Download a video from a URL to the local server using yt-dlp.

    Args:
        url: The URL of the video to download
        path: Optional custom path to save the video (default: ./downloads)
        timeout: Socket timeout in seconds for network operations (default: 30)

    Returns:
        Dict containing metadata about the downloaded file or error message
    """
    try:
        # Run in executor to avoid blocking the async event loop
        return await asyncio.to_thread(
            download_media, url, path or "downloads", timeout
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {"error": "Download failed", "details": str(e)}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
