from fastmcp import FastMCP

from main import search_engine

mcp = FastMCP("Web Search Tools")


@mcp.tool
def search_web(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """Search for general web content."""
    try:
        return search_engine.search(
            query, "text", max_results, time_range, region, sort_by, filter_term
        )
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
    """Search for recent news and current events."""
    try:
        return search_engine.search(
            query, "news", max_results, time_range, region, sort_by, filter_term
        )
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
    """Search for images including photos and visual content."""
    try:
        return search_engine.search(
            query, "image", max_results, time_range, region, sort_by, filter_term
        )
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
    """Search for videos including tutorials and multimedia content."""
    try:
        return search_engine.search(
            query, "video", max_results, time_range, region, sort_by, filter_term
        )
    except Exception as e:
        return {"error": str(e), "query": query, "search_type": "video"}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
