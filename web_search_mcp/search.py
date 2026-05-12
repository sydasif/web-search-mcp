from ddgs import DDGS

from .models import SearchRequest


def _error_dict(query: str, search_type: str, message: str) -> dict:
    return {
        "query": query,
        "search_type": search_type,
        "total_results": 0,
        "results": [],
        "error": message,
    }


def ddg_search(request: SearchRequest) -> dict:
    if not request.query:
        return _error_dict("", request.search_type, "Query cannot be empty")

    kwargs = request.model_dump(exclude_none=True)
    kwargs.pop("query", None)
    kwargs.pop("search_type")
    if "time_range" in kwargs:
        kwargs["timelimit"] = kwargs.pop("time_range")

    try:
        with DDGS() as ddgs:
            search_methods = {"text": ddgs.text, "news": ddgs.news}
            if request.search_type not in search_methods:
                return _error_dict(
                    request.query,
                    request.search_type,
                    f"Unsupported search type: {request.search_type}",
                )

            search_func = search_methods[request.search_type]
            results = list(search_func(request.query, **kwargs))
            return {
                "query": request.query,
                "search_type": request.search_type,
                "total_results": len(results),
                "results": results,
            }
    except Exception as e:
        return _error_dict(request.query, request.search_type, str(e))
