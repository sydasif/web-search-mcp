from ddgs import DDGS


class WebSearch:
    def __init__(self):
        pass

    @staticmethod
    def _create_search_kwargs(max_results=5, time_range=None, region=None):
        kwargs = {"max_results": max_results}
        if time_range:
            kwargs["timelimit"] = time_range
        if region:
            kwargs["region"] = region
        return kwargs

    def search(self, query, search_type="text", max_results=5, time_range=None, region=None, sort_by="relevance", filter_term=None):
        ddgs = DDGS()
        kwargs = self._create_search_kwargs(max_results, time_range, region)

        search_methods = {
            "text": ddgs.text,
            "image": ddgs.images,
            "news": ddgs.news,
            "video": ddgs.videos
        }

        search_func = search_methods.get(search_type, ddgs.text)
        results = search_func(query, **kwargs)

        # Filter results if filter_term provided
        if filter_term:
            filter_term_lower = filter_term.lower()
            results = [
                r for r in results
                if any(
                    isinstance(v, str) and filter_term_lower in v.lower()
                    for v in r.values()
                )
            ]

        # Sort results
        if sort_by == "date":
            results.sort(key=lambda x: x.get("date", x.get("published", "")), reverse=True)
        elif sort_by == "title":
            results.sort(key=lambda x: x.get("title", "").lower())

        return {
            "query": query,
            "search_type": search_type,
            "total_results": len(results),
            "results": results,
        }


# Create instance for server tools
search_engine = WebSearch()
