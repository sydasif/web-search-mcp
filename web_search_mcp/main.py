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
):
    """
    Unified DuckDuckGo search function supporting text, images, news, and videos.

    Args:
        query: Search query string
        search_type: Type of search ('text', 'image', 'news', 'video')
        max_results: Max number of results to return (default 5)
        time_range: Time filter ('d', 'w', 'm', 'y') or None
        region: Geographic region (e.g. 'us-en', 'uk-en') or None
        safesearch: Safe search level ('moderate', 'off', 'on')
        page: Page number for pagination (default 1)
        backend: Backend to use ('auto', 'legacy', 'api')

    Returns:
        Dict with query, search_type, total_results, and results list
    """
    ddgs = DDGS()

    # Prepare kwargs for search with parameters that DDGS actually supports
    kwargs = {
        "max_results": max_results,
        "region": region,
        "safesearch": safesearch,
        "page": page,
        "backend": backend
    }

    # timelimit is the actual parameter name for time_range in DDGS
    if time_range:
        kwargs["timelimit"] = time_range

    # Map search type to appropriate DDGS method
    search_methods = {
        "text": ddgs.text,
        "image": ddgs.images,
        "news": ddgs.news,
        "video": ddgs.videos,
    }

    search_func = search_methods.get(search_type, ddgs.text)
    results = search_func(query, **kwargs)

    return {
        "query": query,
        "search_type": search_type,
        "total_results": len(results),
        "results": results,
    }
