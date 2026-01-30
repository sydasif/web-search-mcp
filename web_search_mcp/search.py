from .providers.async_wrapper import AsyncSearchProviderWrapper
from .providers.duckduckgo import DDGProvider

# Initialize the search provider
_provider = DDGProvider()
search_provider = AsyncSearchProviderWrapper(_provider)


async def ddg_search(
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
    kwargs = {
        "max_results": max_results,
        "time_range": time_range,
        "region": region,
        "safesearch": safesearch,
        "page": page,
        "backend": backend,
        "size": size,
        "color": color,
        "type_image": type_image,
        "layout": layout,
        "license_image": license_image,
        "resolution": resolution,
        "duration": duration,
        "license_videos": license_videos,
    }

    # Filter out None values
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        return await search_provider.search(query, search_type, **kwargs)
    except Exception as e:
        return {
            "query": query,
            "search_type": search_type,
            "total_results": 0,
            "results": [],
            "error": str(e),
        }
