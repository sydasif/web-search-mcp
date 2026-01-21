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
    # Only add parameters that are not None to avoid issues with DDGS library
    kwargs = {}

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
        kwargs["timelimit"] = time_range  # timelimit is the actual parameter name for time_range in DDGS

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
