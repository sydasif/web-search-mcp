from fastmcp import FastMCP

from .main import ddg_search

mcp = FastMCP("Web Search Tools")


@mcp.tool
def search_web(
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
    return ddg_search(
        query, "text", max_results, time_range, region, safesearch, page, backend
    )


@mcp.tool
def search_news(
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
    return ddg_search(
        query, "news", max_results, time_range, region, safesearch, page, backend
    )


@mcp.tool
def search_images(
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
        type_image: Image type ('photo', 'clipart', 'gif', 'transparent', 'line') or None
        layout: Layout filter ('Square', 'Tall', 'Wide') or None
        license_image: License filter (Creative Commons types) or None

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    return ddg_search(
        query,
        "image",
        max_results,
        time_range,
        region,
        safesearch,
        page,
        backend,
        size=size,
        color=color,
        type_image=type_image,
        layout=layout,
        license_image=license_image,
    )


@mcp.tool
def search_videos(
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
    return ddg_search(
        query,
        "video",
        max_results,
        time_range,
        region,
        safesearch,
        page,
        backend,
        resolution=resolution,
        duration=duration,
        license_videos=license_videos,
    )


@mcp.tool
def search_books(
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
    return ddg_search(
        query, "books", max_results, None, None, "moderate", page, backend
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
