"""Web search engines: DuckDuckGo and indirect Exa support via fetch fallback."""

from .ddg import ddg_search, fetch_page, format_search_results_markdown
from .exa import exa_fetch

__all__ = [
    "ddg_search",
    "exa_fetch",
    "fetch_page",
    "format_search_results_markdown",
]
