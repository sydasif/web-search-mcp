from ddgs import DDGS


class WebSearch:
    """A class-based approach to web search functionality."""

    def __init__(self):
        """Initialize the WebSearch class."""
        pass

    @staticmethod
    def _create_search_kwargs(max_results=5, time_range=None, region=None):
        """Helper function to create consistent kwargs for all search types"""
        kwargs = {"max_results": max_results}
        if time_range is not None:
            kwargs["timelimit"] = time_range
        if region is not None:
            kwargs["region"] = region
        return kwargs

    def text_search(self, query, max_results=5, time_range=None, region=None):
        """Perform a text search using DuckDuckGo"""
        ddgs = DDGS()
        kwargs = self._create_search_kwargs(max_results, time_range, region)
        return ddgs.text(query, **kwargs)

    def image_search(self, query, max_results=5, time_range=None, region=None):
        """Perform an image search using DuckDuckGo"""
        ddgs = DDGS()
        kwargs = self._create_search_kwargs(max_results, time_range, region)
        return ddgs.images(query, **kwargs)

    def news_search(self, query, max_results=5, time_range=None, region=None):
        """Perform a news search using DuckDuckGo"""
        ddgs = DDGS()
        kwargs = self._create_search_kwargs(max_results, time_range, region)
        return ddgs.news(query, **kwargs)

    def video_search(self, query, max_results=5, time_range=None, region=None):
        """Perform a video search using DuckDuckGo"""
        ddgs = DDGS()
        kwargs = self._create_search_kwargs(max_results, time_range, region)
        return ddgs.videos(query, **kwargs)

    def filter_and_sort_results(self, results, sort_by="relevance", filter_term=None):
        """Filter and sort search results based on user preferences"""
        filtered_results = results

        # Apply filter if provided
        if filter_term:
            filter_term_lower = filter_term.lower()
            filtered_results = [
                result for result in results
                if any(
                    isinstance(value, str) and filter_term_lower in value.lower()
                    for value in result.values()
                )
            ]

        # Sort results based on sort_by parameter
        if sort_by == "date":
            filtered_results.sort(
                key=lambda x: x.get("date", x.get("published", "")), reverse=True
            )
        elif sort_by == "title":
            filtered_results.sort(key=lambda x: x.get("title", "").lower())

        return filtered_results

    def search(self, query, search_type="text", max_results=5, time_range=None, region=None, sort_by="relevance", filter_term=None):
        """Main search function optimized for LLM consumption"""
        search_methods = {
            "text": self.text_search,
            "image": self.image_search,
            "news": self.news_search,
            "video": self.video_search
        }

        search_method = search_methods.get(search_type, self.text_search)
        results = search_method(query, max_results, time_range, region)
        filtered_results = self.filter_and_sort_results(results, sort_by, filter_term)

        return {
            "query": query,
            "search_type": search_type,
            "total_results": len(filtered_results),
            "results": filtered_results,
        }


# Create a global instance for backward compatibility
search_engine = WebSearch()


# Backward compatibility functions
def text_search(query, max_results=5, time_range=None, region=None):
    return search_engine.text_search(query, max_results, time_range, region)


def image_search(query, max_results=5, time_range=None, region=None):
    return search_engine.image_search(query, max_results, time_range, region)


def news_search(query, max_results=5, time_range=None, region=None):
    return search_engine.news_search(query, max_results, time_range, region)


def video_search(query, max_results=5, time_range=None, region=None):
    return search_engine.video_search(query, max_results, time_range, region)


def search(query, search_type="text", max_results=5, time_range=None, region=None, sort_by="relevance", filter_term=None):
    return search_engine.search(query, search_type, max_results, time_range, region, sort_by, filter_term)
