import logging
from .search import ddg_search
from .models import SearchRequest
from .utils import format_error

logger = logging.getLogger("web-search-mcp")


def search_domain(query: str, domain: str = "docs.python.org") -> dict:
    """Searches specifically for technical documentation on a specified domain.

    Args:
        query: The search query for the documentation.
        domain: The domain to restrict the search to. Defaults to 'docs.python.org'.

    Returns:
        A dictionary containing the search results from the specified domain,
        or a formatted error dictionary on failure.
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
        logger.exception(f"Domain search failed for query '{query}' on domain '{domain}': {e}")
        return format_error("Search failed", str(e))
