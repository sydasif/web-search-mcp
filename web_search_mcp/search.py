import logging
from ddgs import DDGS

from .models import SearchRequest, SearchResponse, SearchResult, ErrorResponse
from .utils import RateLimiter, format_error
from .config import settings

logger = logging.getLogger("web-search-mcp")

# Initialize rate limiter for search
search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_search)


def format_search_results_markdown(results: SearchResponse | ErrorResponse) -> str:
    """Formats search results as a human-readable markdown string.

    Args:
        results: A SearchResponse or ErrorResponse containing the search results.

    Returns:
        A markdown formatted string summarizing the search results.
    """
    if isinstance(results, ErrorResponse):
        return f"**Error:** {results.error}"

    lines = [
        f"# Search Results for '{results.query}' ({results.search_type})",
        f"Found {results.total_results} results.",
        "",
    ]

    if not results.results:
        lines.append("No results found.")
        return "\n".join(lines)

    for i, res in enumerate(results.results, 1):
        url = res.href or res.url or "#"
        lines.append(f"{i}. **[{res.title}]({url})**")
        if res.body:
            lines.append(f"   {res.body}")
        lines.append("")

    if results.has_more and results.next_page:
        lines.append(f"\n*More results available. See page {results.next_page}.*")

    return "\n".join(lines)


def ddg_search(request: SearchRequest) -> SearchResponse | ErrorResponse:
    """Performs a web or news search using DuckDuckGo.

    Args:
        request: A SearchRequest object containing the query and search parameters.

    Returns:
        A SearchResponse containing the search results, or an ErrorResponse on failure.
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
