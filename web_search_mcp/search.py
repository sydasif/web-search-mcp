from ddgs import DDGS

from .models import SearchRequest


def ddg_search(request: SearchRequest) -> dict:
    """
    Unified DuckDuckGo search function supporting text and news search.

    Args:
        request: SearchRequest object containing all search parameters

    Returns:
        Dict with query, search_type, total_results, and results list
    """
    if not request.query:
        return {
            "query": "",
            "search_type": request.search_type,
            "total_results": 0,
            "results": [],
            "error": "Query cannot be empty",
        }

    # Extract all parameters from the request model
    kwargs = request.model_dump(exclude={"query", "search_type", "filters"})

    # Merge additional filters if present
    if request.filters:
        kwargs.update(request.filters)

    # Filter out None values
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        with DDGS() as ddgs:
            # Map search type to DDGS method
            search_methods = {
                "text": ddgs.text,
                "news": ddgs.news,
            }

            if request.search_type not in search_methods:
                return {
                    "query": request.query,
                    "search_type": request.search_type,
                    "total_results": 0,
                    "results": [],
                    "error": f"Unsupported search type: {request.search_type}",
                }

            search_func = search_methods[request.search_type]

            search_kwargs = {
                "max_results": kwargs.get("max_results"),
                "region": kwargs.get("region"),
                "safesearch": kwargs.get("safesearch"),
                "page": kwargs.get("page"),
                "backend": kwargs.get("backend"),
                "timelimit": kwargs.get("time_range"),
            }
            search_kwargs = {k: v for k, v in search_kwargs.items() if v is not None}

            results = list(search_func(request.query, **search_kwargs))
            return {
                "query": request.query,
                "search_type": request.search_type,
                "total_results": len(results),
                "results": results,
            }
    except Exception as e:
        return {
            "query": request.query,
            "search_type": request.search_type,
            "total_results": 0,
            "results": [],
            "error": str(e),
        }
