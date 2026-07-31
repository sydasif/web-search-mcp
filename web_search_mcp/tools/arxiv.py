"""arXiv paper search via the official arXiv API.

Uses the arxiv Python library (v4+) for searching academic papers by
keyword, author, or category. Free, no API key required.
"""

from __future__ import annotations

import logging
from typing import Literal

import arxiv  # type: ignore[import-untyped]

from .._models import ErrorResponse
from .._utils import format_results_markdown

logger = logging.getLogger(__name__)

# Categories for sorting results
SortCriterion = Literal["relevance", "submitted_date", "updated_date"]

_CRITERION_MAP: dict[str, arxiv.SortCriterion] = {
    "relevance": arxiv.SortCriterion.Relevance,
    "submitted_date": arxiv.SortCriterion.SubmittedDate,
    "updated_date": arxiv.SortCriterion.LastUpdatedDate,
}

MAX_RESULTS_CAP = 50


def _search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: SortCriterion = "relevance",
) -> list[dict] | ErrorResponse:
    """Search arXiv for academic papers.

    Args:
        query: Search query (e.g. 'transformer attention', 'au:Goodfellow',
               'cat:cs.AI'). Supports Lucene syntax: all:, ti:, au:, abs:,
               cat: prefixes.
        max_results: Max results to return (capped at 50).
        sort_by: Sort criterion ('relevance', 'submitted_date', 'updated_date').

    Returns:
        List of paper dicts with title, authors, summary, pdf_url,
        published date, and categories. Returns ErrorResponse on failure.

    """
    if not query.strip():
        return ErrorResponse(
            error="Query cannot be empty", details="Provide a non-empty search query."
        )

    client = arxiv.Client(
        page_size=min(max_results, MAX_RESULTS_CAP),
        delay_seconds=3,
        num_retries=3,
    )

    sort_criterion = _CRITERION_MAP.get(sort_by, arxiv.SortCriterion.Relevance)

    try:
        search = arxiv.Search(
            query=query.strip(),
            max_results=min(max_results, MAX_RESULTS_CAP),
            sort_by=sort_criterion,
            sort_order=arxiv.SortOrder.Descending,
            id_list=[],
        )

        results = list(client.results(search))

        papers: list[dict] = []
        for r in results:
            papers.append(
                {
                    "id": r.entry_id,
                    "title": r.title,
                    "authors": [a.name for a in r.authors],
                    "summary": r.summary,
                    "pdf_url": r.pdf_url,
                    "published": str(r.published.date()) if r.published else "",
                    "updated": str(r.updated.date()) if r.updated else "",
                    "primary_category": str(r.primary_category) if r.primary_category else "",
                    "categories": [str(c) for c in r.categories],
                    "comment": r.comment or "",
                    "journal_ref": r.journal_ref or "",
                    "doi": r.doi or "",
                }
            )

        return papers
    except Exception as e:
        logger.exception("arXiv search failed")
        return ErrorResponse(
            error=f"arXiv search failed: {e}",
            details="Try a different query or check arXiv's status at export.arxiv.org.",
        )


def _format_arxiv_markdown(papers: list[dict], query: str) -> str:
    """Format arXiv results as markdown."""

    def _item_lines(paper: dict, i: int) -> list[str]:
        authors = paper.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."
        cat_str = ", ".join(paper.get("categories", [])[:3])

        lines = [
            f"{i}. **[{paper.get('title', 'Untitled')}]({paper.get('pdf_url', '#')})**",
            f"   {author_str}",
        ]
        if paper.get("published"):
            lines.append(f"   📅 {paper['published']}")
        if cat_str:
            lines.append(f"   📂 {cat_str}")
        summary = paper.get("summary", "")
        if summary:
            truncated = summary[:300].replace("\n", " ")
            lines.append(f"   {truncated}...")
        return lines

    return format_results_markdown(papers, query, "arXiv", "papers", _item_lines)


def arxiv_search_tool(
    query: str,
    max_results: int = 10,
    sort_by: SortCriterion = "relevance",
) -> str | ErrorResponse:
    """Search arXiv for academic papers — free, no API key needed."""
    result = _search_arxiv(query=query, max_results=max_results, sort_by=sort_by)
    if isinstance(result, ErrorResponse):
        return result

    if not result:
        return f"No arXiv papers found for '{query}'."

    return _format_arxiv_markdown(result, query)
