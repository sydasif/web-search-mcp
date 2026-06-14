"""Web search engines: DuckDuckGo and Exa AI."""

from .ddg import ddg_search, fetch_page, format_search_results_markdown
from .exa import exa_fetch, exa_search, exa_search_advanced

__all__ = [
    "ddg_search",
    "exa_fetch",
    "exa_search",
    "exa_search_advanced",
    "fetch_page",
    "format_search_results_markdown",
]
