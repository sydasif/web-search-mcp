from .search import ddg_search
from .models import SearchRequest


def search_docs(query: str, tech_stack: str = "python") -> dict:
    """
    Searches specifically for technical documentation.

    Args:
        query: What you're looking for in the docs
        tech_stack: Which technology's docs to search (python, react, mcp)

    Returns:
        Search results from the specified documentation site
    """
    site_map = {
        "python": "docs.python.org",
        "react": "react.dev",
        "mcp": "modelcontextprotocol.io",
        "fastapi": "fastapi.tiangolo.com",
        "httpx": "www.python-httpx.org",
    }
    site = site_map.get(tech_stack, site_map["python"])
    enhanced_query = f"site:{site} {query}"

    try:
        req = SearchRequest(
            query=enhanced_query,
            search_type="text",
            max_results=5,
        )
        return ddg_search(req)
    except Exception as e:
        return {"error": "Search failed", "details": str(e)}
