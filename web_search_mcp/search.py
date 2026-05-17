import logging
from ddgs import DDGS

from .models import SearchRequest
from .utils import RateLimiter, format_error
from .config import settings

logger = logging.getLogger("web-search-mcp")

# Initialize rate limiter for search
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)


def format_search_results_markdown(results_dict: dict) -> str:
    """Formats search results as a human-readable markdown string.

    Args:
        results_dict: A dictionary containing the search results, including 'query',
            'search_type', 'total_results', and 'results'.

    Returns:
        A markdown formatted string summarizing the search results.
    """
    if "error" in results_dict:
        return f"**Error:** {results_dict['error']}"

    query = results_dict.get("query", "N/A")
    search_type = results_dict.get("search_type", "text")
    total = results_dict.get("total_results", 0)
    results = results_dict.get("results", [])

    lines = [f"# Search Results for '{query}' ({search_type})", f"Found {total} results.", ""]

    if not results:
        lines.append("No results found.")
        return "\n".join(lines)

    for i, res in enumerate(results, 1):
        title = res.get("title", "No Title")
        url = res.get("href") or res.get("url", "#")
        body = res.get("body", "")
        lines.append(f"{i}. **[{title}]({url})**")
        if body:
            lines.append(f"   {body}")
        lines.append("")

    if results_dict.get("has_more"):
        lines.append(f"\n*More results available. See page {results_dict['next_page']}.*")

    return "\n".join(lines)


def ddg_search(request: SearchRequest) -> dict:
    """Performs a web or news search using DuckDuckGo.

    Args:
        request: A SearchRequest object containing the query and search parameters.

    Returns:
        A dictionary containing the search results, total count, and pagination info,
        or a formatted error dictionary on failure.
    """
    if not request.query:
        return format_error("Query cannot be empty")

    # Apply rate limiting
    search_rate_limiter.acquire()

    kwargs = request.model_dump(exclude_none=True)
    kwargs.pop("query", None)
    kwargs.pop("search_type", None)
    kwargs.pop("response_format", None)
    if "time_range" in kwargs:
        kwargs["timelimit"] = kwargs.pop("time_range")

    try:
        with DDGS() as ddgs:
            search_methods = {"text": ddgs.text, "news": ddgs.news}
            if request.search_type not in search_methods:
                return format_error(f"Unsupported search type: {request.search_type}")

            search_func = search_methods[request.search_type]
            results = list(search_func(request.query, **kwargs))

            # DDGS returns one page of results.
            # If we got the maximum requested results, there might be more.
            has_more = len(results) >= request.max_results

            return {
                "query": request.query,
                "search_type": request.search_type,
                "total_results": len(results),
                "results": results,
                "has_more": has_more,
                "next_page": request.page + 1 if has_more else None,
            }
    except Exception as e:
        logger.exception(f"DuckDuckGo search failed for query '{request.query}': {e}")
        return format_error(str(e))
