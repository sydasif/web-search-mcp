from .models import SearchRequest
from .providers.async_wrapper import AsyncSearchProviderWrapper
from .providers.duckduckgo import DDGProvider

# Initialize the search provider
_provider = DDGProvider()
search_provider = AsyncSearchProviderWrapper(_provider)


async def ddg_search(request: SearchRequest):
    """
    Unified DuckDuckGo search function supporting text, images, news, videos, and books.

    Args:
        request: SearchRequest object containing all search parameters

    Returns:
        Dict with query, search_type, total_results, and results list
    """
    # Extract all parameters from the request model
    kwargs = request.model_dump(exclude={"query", "search_type", "filters"})

    # Merge additional filters if present
    if request.filters:
        kwargs.update(request.filters)

    # Filter out None values
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        return await search_provider.search(
            request.query, request.search_type, **kwargs
        )
    except Exception as e:
        return {
            "query": request.query,
            "search_type": request.search_type,
            "total_results": 0,
            "results": [],
            "error": str(e),
        }
