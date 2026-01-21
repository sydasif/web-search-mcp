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
    try:
        return ddg_search(
            query, "text", max_results, time_range, region, safesearch, page, backend
        )
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "text"}


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
    try:
        return ddg_search(
            query, "news", max_results, time_range, region, safesearch, page, backend
        )
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "news"}


@mcp.tool
def search_images(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
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

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    try:
        return ddg_search(
            query, "image", max_results, time_range, region, safesearch, page, backend
        )
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "image"}


@mcp.tool
def search_videos(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "auto",
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

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
    try:
        return ddg_search(
            query, "video", max_results, time_range, region, safesearch, page, backend
        )
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "video"}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
