from typing import Any

from ddgs import DDGS

from .base import SearchProvider


class DDGProvider(SearchProvider):
    def __init__(self):
        # Initialize configuration here if needed
        pass

    def search(self, query: str, search_type: str, **kwargs) -> dict[str, Any]:
        """
        Synchronous search implementation using DDGS.
        This method is designed to be called in a thread pool executor
        to avoid blocking the async event loop.
        """
        with DDGS() as ddgs:
            # Prepare kwargs for search with parameters that DDGS actually supports
            # Only add parameters that are not None to avoid issues with DDGS library
            search_kwargs = {}

            # Common parameters for all search types
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
            if search_type == "image":
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
            if search_type == "video":
                if kwargs.get("resolution") is not None:
                    search_kwargs["resolution"] = kwargs["resolution"]
                if kwargs.get("duration") is not None:
                    search_kwargs["duration"] = kwargs["duration"]
                if kwargs.get("license_videos") is not None:
                    search_kwargs["license_videos"] = kwargs["license_videos"]

            # Map search type to appropriate DDGS method
            search_methods = {
                "text": ddgs.text,
                "image": ddgs.images,
                "news": ddgs.news,
                "video": ddgs.videos,
                "books": ddgs.books,
            }

            search_func = search_methods.get(search_type, ddgs.text)

            try:
                results = search_func(query, **search_kwargs)
                return {
                    "query": query,
                    "search_type": search_type,
                    "total_results": len(results),
                    "results": results,
                }
            except Exception as e:
                return {
                    "query": query,
                    "search_type": search_type,
                    "total_results": 0,
                    "results": [],
                    "error": str(e),
                }
