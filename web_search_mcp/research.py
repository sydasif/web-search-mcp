from .search import ddg_search
from .models import SearchRequest


def search_domain(query: str, domain: str = "docs.python.org") -> dict:
    """
    Searches specifically for technical documentation on a specific domain.

    Args:
        query: What you're looking for in the docs
        domain: The domain to search (e.g., 'docs.python.org', 'github.com')

    Returns:
        Search results from the specified domain
    """
    enhanced_query = f"site:{domain} {query}"

    try:
        req = SearchRequest(
            query=enhanced_query,
            search_type="text",
            max_results=5,
        )
        return ddg_search(req)
    except Exception as e:
        return {"error": "Search failed", "details": str(e)}
