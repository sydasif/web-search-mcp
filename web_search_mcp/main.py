from ddgs import DDGS


def ddg_search(
    query,
    search_type="text",
    max_results=5,
    time_range=None,  # maps to timelimit in DDGS
    region=None,
    safesearch="moderate",
    page=1,
    backend="auto",
    # Additional parameters for enhanced filtering
    size=None,  # images: "Small", "Medium", "Large", "Wallpaper"
    color=None,  # images: color name or "Monochrome"
    type_image=None,  # images: "photo", "clipart", "gif", "transparent", "line"
    layout=None,  # images: "Square", "Tall", "Wide"
    license_image=None,  # images: license types
    resolution=None,  # videos: "high", "standart"
    duration=None,  # videos: "short", "medium", "long"
    license_videos=None,  # videos: "creativeCommon", "youtube"
):
    """
    Unified DuckDuckGo search function supporting text, images, news, videos, and books.

    Args:
        query: Search query string
        search_type: Type of search ('text', 'image', 'news', 'video', 'books')
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')
        size: Image size filter ('Small', 'Medium', 'Large', 'Wallpaper')
        color: Image color filter (color name or 'Monochrome')
        type_image: Image type filter ('photo', 'clipart', 'gif', 'transparent', 'line')
        layout: Image layout filter ('Square', 'Tall', 'Wide')
        license_image: Image license filter (various Creative Commons types)
        resolution: Video resolution filter ('high', 'standart')
        duration: Video duration filter ('short', 'medium', 'long')
        license_videos: Video license filter ('creativeCommon', 'youtube')

    Returns:
        Dict with query, search_type, total_results, and results list
    """
    # Use context manager for proper resource cleanup
    with DDGS() as ddgs:
        # Prepare kwargs for search with parameters that DDGS actually supports
        # Only add parameters that are not None to avoid issues with DDGS library
        kwargs = {}

        # Common parameters for all search types
        if max_results is not None:
            kwargs["max_results"] = max_results
        if region is not None:
            kwargs["region"] = region
        if safesearch is not None:
            kwargs["safesearch"] = safesearch
        if page is not None:
            kwargs["page"] = page
        if backend is not None:
            kwargs["backend"] = backend
        if time_range is not None:
            kwargs["timelimit"] = (
                time_range  # timelimit is the actual parameter name for time_range in DDGS
            )

        # Image-specific parameters
        if search_type == "image":
            if size is not None:
                kwargs["size"] = size
            if color is not None:
                kwargs["color"] = color
            if type_image is not None:
                kwargs["type_image"] = type_image
            if layout is not None:
                kwargs["layout"] = layout
            if license_image is not None:
                kwargs["license_image"] = license_image

        # Video-specific parameters
        if search_type == "video":
            if resolution is not None:
                kwargs["resolution"] = resolution
            if duration is not None:
                kwargs["duration"] = duration
            if license_videos is not None:
                kwargs["license_videos"] = license_videos

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
            results = search_func(query, **kwargs)
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
