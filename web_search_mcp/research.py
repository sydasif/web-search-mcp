import wikipedia
import arxiv

from .search import ddg_search
from .models import SearchRequest


def search_wiki(query: str) -> dict:
    """Searches Wikipedia for summaries."""
    try:
        search_results = wikipedia.search(query)
        if not search_results:
            return {"results": [], "message": "No Wikipedia pages found."}

        page = wikipedia.page(search_results[0], auto_suggest=False)
        return {
            "title": page.title,
            "summary": page.summary[:2000],
            "url": page.url,
            "related_topics": search_results[1:5],
        }
    except Exception as e:
        return {"error": str(e)}


def search_arxiv(query: str, max_results: int = 3) -> list:
    """Searches for scientific papers on ArXiv."""
    try:
        search = arxiv.Search(
            query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance
        )
        return [
            {
                "title": r.title,
                "summary": r.summary,
                "authors": [a.name for a in r.authors],
                "url": r.pdf_url,
                "published": r.published.strftime("%Y-%m-%d"),
            }
            for r in search.results()
        ]
    except Exception as e:
        return [{"error": str(e)}]


def search_docs(query: str, tech_stack: str = "python") -> dict:
    """
    Searches specifically for technical documentation.

    Args:
        query: What you're looking for in the docs
        tech_stack: Which technology's docs to search (python, react, mcp)

    Returns:
        Search results from the specified documentation site
    """
    site_map = {
        "python": "docs.python.org",
        "react": "react.dev",
        "mcp": "modelcontextprotocol.io",
        "fastapi": "fastapi.tiangolo.com",
        "httpx": "www.python-httpx.org",
    }
    site = site_map.get(tech_stack, site_map["python"])
    enhanced_query = f"site:{site} {query}"

    try:
        req = SearchRequest(
            query=enhanced_query,
            search_type="text",
            max_results=5,
        )
        return ddg_search(req)
    except Exception as e:
        return {"error": "Search failed", "details": str(e)}
