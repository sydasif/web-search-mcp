from fastmcp import FastMCP

from main import search  # Import the search functionality from main.py

# Create your MCP server
mcp = FastMCP("Web Search Tools")


# Add the search functionality as an MCP tool
@mcp.tool
def web_search_tool(
    query: str,
    search_type: str = "text",
    max_results: int = 5,
    time_range: str | None = None,
    region: str | None = None,
    sort_by: str = "relevance",
    filter_term: str | None = None,
) -> dict:
    """
    Perform web searches across multiple content types using DuckDuckGo.

    Choose the appropriate search type based on your needs:

    **search_type options:**
    - "text" (default): Web pages, articles, blogs, documentation, tutorials
    - "news": Recent news articles, current events, breaking stories
    - "image": Photos, diagrams, infographics, visual content
    - "video": Video tutorials, demonstrations, talks, media content

    **Examples:**
    - Use "news" for: "latest AI developments", "current climate news"
    - Use "image" for: "neural network diagrams", "robot photos"
    - Use "video" for: "Python tutorials", "AI explanations"
    - Use "text" for: general research, documentation, articles

    Args:
        query: Search query string
        search_type: Content type to search for ("text", "news", "image", "video")
        max_results: Number of results to return (1-20, default: 5)
        time_range: Time filter ("day", "week", "month", "year")
        region: Region code ("us", "uk", "de", etc.)
        sort_by: Sort method ("relevance", "date", "title")
        filter_term: Only show results containing this word/phrase

    Returns:
        Dictionary with search results, including titles, URLs, and descriptions
    """
    try:
        # Call the search function from main.py (returns dict directly)
        result = search(
            query=query,
            search_type=search_type,
            max_results=max_results,
            time_range=time_range,
            region=region,
            sort_by=sort_by,
            filter_term=filter_term,
        )

        return result

    except Exception as e:
        return {"error": str(e), "query": query, "search_type": search_type}


if __name__ == "__main__":
    # Run with STDIO transport for Claude Code
    mcp.run(transport="stdio")
