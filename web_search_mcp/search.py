from ddgs import DDGS

from .models import SearchRequest


def ddg_search(request: SearchRequest):
    """
    Unified DuckDuckGo search function supporting text, images, news, videos, and books.

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
                "web": ddgs.text,
                "image": ddgs.images,
                "images": ddgs.images,
                "news": ddgs.news,
                "video": ddgs.videos,
                "videos": ddgs.videos,
                "books": ddgs.books,
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

            # Prepare kwargs for DDGS
            search_kwargs = {}
            if kwargs.get("max_results") is not None:
                search_kwargs["max_results"] = kwargs["max_results"]
            if kwargs.get("region") is not None:
                search_kwargs["region"] = kwargs["region"]
            if kwargs.get("safesearch") is not None:
                search_kwargs["safesearch"] = kwargs["safesearch"]
            if kwargs.get("page") is not None:
                search_kwargs["page"] = kwargs["page"]
            if kwargs.get("backend") is not None:
                search_kwargs["backend"] = kwargs["backend"]
            if kwargs.get("time_range") is not None:
                search_kwargs["timelimit"] = kwargs["time_range"]

            # Image-specific parameters
            if request.search_type == "image":
                if kwargs.get("size") is not None:
                    search_kwargs["size"] = kwargs["size"]
                if kwargs.get("color") is not None:
                    search_kwargs["color"] = kwargs["color"]
                if kwargs.get("type_image") is not None:
                    search_kwargs["type_image"] = kwargs["type_image"]
                if kwargs.get("layout") is not None:
                    search_kwargs["layout"] = kwargs["layout"]
                if kwargs.get("license_image") is not None:
                    search_kwargs["license_image"] = kwargs["license_image"]

            # Video-specific parameters
            if request.search_type == "video":
                if kwargs.get("resolution") is not None:
                    search_kwargs["resolution"] = kwargs["resolution"]
                if kwargs.get("duration") is not None:
                    search_kwargs["duration"] = kwargs["duration"]
                if kwargs.get("license_videos") is not None:
                    search_kwargs["license_videos"] = kwargs["license_videos"]

            results = search_func(request.query, **search_kwargs)
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
