import logging
from ddgs import DDGS

from .models import SearchRequest, SearchResponse, SearchResult, ErrorResponse
from .utils import RateLimiter, format_error
from .config import settings

logger = logging.getLogger("web-search-mcp")

# Initialize rate limiter for search
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)


def format_search_results_markdown(results: SearchResponse | ErrorResponse | dict) -> str:
    """Formats search results as a human-readable markdown string.

    Args:
        results: A SearchResponse, ErrorResponse, or a dictionary containing the search results.

    Returns:
        A markdown formatted string summarizing the search results.
    """
    # Handle ErrorResponse or dict with error
    if isinstance(results, ErrorResponse) or (isinstance(results, dict) and "error" in results):
        err_msg = (
            results.error
            if isinstance(results, ErrorResponse)
            else results.get("error", "Unknown error")
        )
        return f"**Error:** {err_msg}"

    # Handle dict for backward compatibility
    if isinstance(results, dict):
        query = results.get("query", "N/A")
        search_type = results.get("search_type", "text")
        total = results.get("total_results", 0)
        results_list = results.get("results", [])
        has_more = results.get("has_more", False)
        next_page = results.get("next_page")
    else:
        # results is a SearchResponse
        query = results.query
        search_type = results.search_type
        total = results.total_results
        results_list = results.results
        has_more = results.has_more
        next_page = results.next_page

    lines = [f"# Search Results for '{query}' ({search_type})", f"Found {total} results.", ""]

    if not results_list:
        lines.append("No results found.")
        return "\n".join(lines)

    for i, res in enumerate(results_list, 1):
        # Support both SearchResult model and dict
        if isinstance(res, SearchResult):
            title = res.title
            url = res.href or res.url or "#"
            body = res.body
        else:
            title = res.get("title", "No Title")
            url = res.get("href") or res.get("url", "#")
            body = res.get("body", "")

        lines.append(f"{i}. **[{title}]({url})**")
        if body:
            lines.append(f"   {body}")
        lines.append("")

    if has_more and next_page:
        lines.append(f"\n*More results available. See page {next_page}.*")

    return "\n".join(lines)


def ddg_search(request: SearchRequest) -> SearchResponse | ErrorResponse:
    """Performs a web or news search using DuckDuckGo.

    Args:
        request: A SearchRequest object containing the query and search parameters.

    Returns:
        A SearchResponse object containing the search results, or a formatted error dictionary.
    """
    if not request.query:
        return format_error("Query cannot be empty")

    # Apply rate limiting
    search_rate_limiter.acquire()

    kwargs = request.model_dump(
        exclude={"query", "search_type", "response_format"}, exclude_none=True
    )
    if "time_range" in kwargs:
        kwargs["timelimit"] = kwargs.pop("time_range")

    try:
        with DDGS() as ddgs:
            search_methods = {"text": ddgs.text, "news": ddgs.news}
            if request.search_type not in search_methods:
                return format_error(f"Unsupported search type: {request.search_type}")

            search_func = search_methods[request.search_type]
            raw_results = list(search_func(request.query, **kwargs))

            # DDGS returns one page of results.
            has_more = len(raw_results) >= request.max_results

            return SearchResponse(
                query=request.query,
                search_type=request.search_type,
                total_results=len(raw_results),
                results=[SearchResult(**res) for res in raw_results],
                has_more=has_more,
                next_page=request.page + 1 if has_more else None,
            )
    except Exception as e:
        logger.exception(f"DuckDuckGo search failed for query '{request.query}': {e}")
        return format_error(str(e))
