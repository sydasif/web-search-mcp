import asyncio
import logging
import ssl
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastmcp import FastMCP

from .config import settings
from .models import SearchRequest
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


@mcp.tool
async def search(
    query: str,
    search_type: Literal["text", "image", "news", "video", "books"] = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
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
        filters: Additional type-specific filters (e.g., {"size": "Large"} for images)

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
            filters=filters,
        )
        return await ddg_search(req)
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


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
