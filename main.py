from ddgs import DDGS


def text_search(query, max_results=5, time_range=None, region=None):
    """Perform a text search using DuckDuckGo"""
    ddgs = DDGS()
    kwargs = {"max_results": max_results}
    if time_range is not None:
        kwargs["timelimit"] = time_range
    if region is not None:
        kwargs["region"] = region
    results = ddgs.text(query, **kwargs)
    return results


def image_search(query, max_results=5, time_range=None, region=None):
    """Perform an image search using DuckDuckGo"""
    ddgs = DDGS()
    kwargs = {"max_results": max_results}
    if time_range is not None:
        kwargs["timelimit"] = time_range
    if region is not None:
        kwargs["region"] = region
    results = ddgs.images(query, **kwargs)
    return results


def news_search(query, max_results=5, time_range=None, region=None):
    """Perform a news search using DuckDuckGo"""
    ddgs = DDGS()
    kwargs = {"max_results": max_results}
    if time_range is not None:
        kwargs["timelimit"] = time_range
    if region is not None:
        kwargs["region"] = region
    results = ddgs.news(query, **kwargs)
    return results


def video_search(query, max_results=5, time_range=None, region=None):
    """Perform a video search using DuckDuckGo"""
    ddgs = DDGS()
    kwargs = {"max_results": max_results}
    if time_range is not None:
        kwargs["timelimit"] = time_range
    if region is not None:
        kwargs["region"] = region
    results = ddgs.videos(query, **kwargs)
    return results


def filter_and_sort_results(results, sort_by="relevance", filter_term=None):
    """Filter and sort search results based on user preferences"""
    filtered_results = results

    # Apply filter if provided
    if filter_term:
        filter_term_lower = filter_term.lower()
        filtered_results = []
        for result in results:
            # Check if filter term is in title, body, or other fields
            match_found = False
            for value in result.values():
                if isinstance(value, str) and filter_term_lower in value.lower():
                    match_found = True
                    break
            if match_found:
                filtered_results.append(result)

    # Sort results based on sort_by parameter
    if sort_by == "date":
        # For results that have date information
        filtered_results.sort(
            key=lambda x: x.get("date", x.get("published", "")), reverse=True
        )
    elif sort_by == "title":
        # Sort by title
        filtered_results.sort(key=lambda x: x.get("title", "").lower())
    elif sort_by == "relevance":
        # Keep original order (already ordered by relevance from the search engine)
        pass

    return filtered_results


def search(
    query,
    search_type="text",
    max_results=5,
    time_range=None,
    region=None,
    sort_by="relevance",
    filter_term=None,
):
    """
    Main search function optimized for LLM consumption
    Returns structured data as a dictionary
    """
    results = []

    if search_type == "text":
        results = text_search(query, max_results, time_range, region)
    elif search_type == "image":
        results = image_search(query, max_results, time_range, region)
    elif search_type == "news":
        results = news_search(query, max_results, time_range, region)
    elif search_type == "video":
        results = video_search(query, max_results, time_range, region)
    else:
        results = text_search(query, max_results, time_range, region)  # default to text

    # Apply filtering and sorting
    filtered_results = filter_and_sort_results(results, sort_by, filter_term)

    # Return structured data optimized for LLM consumption
    return {
        "query": query,
        "search_type": search_type,
        "total_results": len(filtered_results),
        "results": filtered_results,
    }
