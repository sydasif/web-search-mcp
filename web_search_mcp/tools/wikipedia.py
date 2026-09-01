"""Wikipedia search and article reading via MediaWiki API.

Uses the MediaWiki action API with ``explaintext`` for clean,
section-marked plain text extraction. No API key required.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote, urlencode

from .._http import get_json_client
from .._utils import truncate_content

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
TIMEOUT = 15
MAX_RESULTS_CAP = 20


def _search_wikipedia(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search Wikipedia for articles matching the query."""
    capped = min(max_results, MAX_RESULTS_CAP)
    params: dict[str, str] = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": str(capped),
        "srprop": "snippet|size|wordcount|timestamp",
    }
    url = f"{WIKI_API}?{urlencode(params)}"
    logger.info("Wikipedia searching for '%s' (max=%d)", query, capped)

    try:
        with get_json_client(timeout=TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Wikipedia search failed")
        return []

    hits = data.get("query", {}).get("search", [])
    logger.info("Wikipedia found %d results", len(hits))

    results: list[dict[str, Any]] = []
    for hit in hits:
        title = hit.get("title", "")
        pageid = hit.get("pageid")
        if not title or not pageid:
            continue
        results.append(
            {
                "title": title,
                "pageid": pageid,
                "snippet": hit.get("snippet", ""),
                "wordcount": hit.get("wordcount", 0),
                "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}",
                "timestamp": hit.get("timestamp", ""),
            },
        )

    return results


def _fetch_page_extract(title: str) -> str | None:
    """Fetch the full article text for a Wikipedia title."""
    params: dict[str, str] = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exlimit": "1",
        "explaintext": "1",
        "titles": title,
    }
    url = f"{WIKI_API}?{urlencode(params)}"

    try:
        with get_json_client(timeout=TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Wikipedia page fetch failed for '%s': %s", title, e)
        return None

    pages = data.get("query", {}).get("pages", {})
    for page_id, page_info in pages.items():
        if page_id == "-1":
            return None
        extract = page_info.get("extract")
        if extract:
            return extract.strip()
    return None


def wikipedia_search_tool(query: str, max_results: int = 5) -> str:
    """Search Wikipedia and return the top article + related results..
    query = query.strip()
    if not query:
        return "_Error: Empty query._\n"

    results = _search_wikipedia(query, max_results=max_results)
    if not results:
        return f"_No Wikipedia articles found for '{query}'._\n"

    lines: list[str] = []

    # ── top result: full article text ──
    top = results[0]
    title = top["title"]
    url = top["url"]

    lines.append(f"# Wikipedia: {title}")
    lines.append("")
    lines.append(f"**URL:** {url}")

    wordcount = top.get("wordcount", 0)
    if wordcount:
        formatted_wc = f"{wordcount:,}"
        lines.append(f"**Word count:** {formatted_wc}")
    lines.append("")

    content = _fetch_page_extract(title)
    if content:
        lines.append(content)
        lines.append("")
    else:
        lines.append("*Article text unavailable.*")
        lines.append("")

    # ── related results ──
    if len(results) > 1:
        lines.append("---")
        lines.append("")
        lines.append("### Related results")
        lines.append("")
        for r in results[1:]:
            wc = r.get("wordcount", 0)
            wc_str = f" — {wc:,} words" if wc else ""
            lines.append(f"- [{r['title']}]({r['url']}){wc_str}")
        lines.append("")

    md = "\n".join(lines).strip() + "\n"

    return truncate_content(md, "WIKIPEDIA_MAX_CHARS")
