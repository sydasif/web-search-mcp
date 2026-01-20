from fastmcp import FastMCP
from main import WebSearch

# Create search engine instance
search_engine = WebSearch()

mcp = FastMCP("Web Search Tools")


# Define 4 separate tools with consistent implementation
@mcp.tool
def search_web(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """
    Search for general web content including articles, documentation, tutorials, and blog posts.

    Args:
        query: The search query string
        max_results: Number of results (1-20, default: 5)
        time_range: Filter by time - "day", "week", "month", "year" (optional)
        region: Region code like "us", "uk", "de" for localized results (optional)
        sort_by: Sort results by "relevance", "date", or "title" (default: "relevance")
        filter_term: Only include results containing this word/phrase (optional)

    Returns:
        Dictionary with web page results including title, href (URL), and body (description)
    """
    try:
        result = search_engine.search(
            query=query,
            search_type="text",
            max_results=max_results,
            time_range=time_range,
            region=region,
            sort_by=sort_by,
            filter_term=filter_term,
        )
        return result
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "text"}


@mcp.tool
def search_news(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """
    Search for recent news and current events with publication dates and sources.

    Args:
        query: The search query string
        max_results: Number of results (1-20, default: 5)
        time_range: Filter by time - "day", "week", "month", "year" (optional)
        region: Region code like "us", "uk", "de" for localized results (optional)
        sort_by: Sort results by "relevance", "date", or "title" (default: "relevance")
        filter_term: Only include results containing this word/phrase (optional)

    Returns:
        Dictionary with news results including date, title, body, url, image, and source
    """
    try:
        result = search_engine.search(
            query=query,
            search_type="news",
            max_results=max_results,
            time_range=time_range,
            region=region,
            sort_by=sort_by,
            filter_term=filter_term,
        )
        return result
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "news"}


@mcp.tool
def search_images(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """
    Search for images including photos, diagrams, charts, and visual content.

    Args:
        query: The search query string
        max_results: Number of results (1-20, default: 5)
        time_range: Filter by time - "day", "week", "month", "year" (optional)
        region: Region code like "us", "uk", "de" for localized results (optional)
        sort_by: Sort results by "relevance", "date", or "title" (default: "relevance")
        filter_term: Only include results containing this word/phrase (optional)

    Returns:
        Dictionary with image results including title, image URL, thumbnail, dimensions, and source
    """
    try:
        result = search_engine.search(
            query=query,
            search_type="image",
            max_results=max_results,
            time_range=time_range,
            region=region,
            sort_by=sort_by,
            filter_term=filter_term,
        )
        return result
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "image"}


@mcp.tool
def search_videos(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """
    Search for videos including tutorials, demonstrations, lectures, and multimedia content.

    Args:
        query: The search query string
        max_results: Number of results (1-20, default: 5)
        time_range: Filter by time - "day", "week", "month", "year" (optional)
        region: Region code like "us", "uk", "de" for localized results (optional)
        sort_by: Sort results by "relevance", "date", or "title" (default: "relevance")
        filter_term: Only include results containing this word/phrase (optional)

    Returns:
        Dictionary with video results including title, description, duration, images, statistics, and metadata
    """
    try:
        result = search_engine.search(
            query=query,
            search_type="video",
            max_results=max_results,
            time_range=time_range,
            region=region,
            sort_by=sort_by,
            filter_term=filter_term,
        )
        return result
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "video"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
