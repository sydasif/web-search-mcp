"""Techmeme tech-news search via techmeme-pp-cli (free, no auth required).

Shells out to techmeme-pp-cli to search Techmeme's live archive (2005+).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from typing import Any

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._models import ErrorResponse, SearchResponse
from .._models.types import Depth
from .._utils import format_results_markdown, token_overlap_relevance

logger = logging.getLogger(__name__)

CLI_BIN = "techmeme-pp-cli"

DEPTH_CONFIG = _ALL_DEPTH_LIMITS.get("techmeme", {"quick": 8, "default": 16, "deep": 30})
MIN_HEADLINE_WORDS = 4
SEARCH_TIMEOUT = 30
_NO_RESULTS_PREFIX = "No results"
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _log(msg: str) -> None:
    logger.debug("[Techmeme] %s", msg)


def is_available() -> bool:
    """True when the techmeme-pp-cli binary is on PATH."""
    return shutil.which(CLI_BIN) is not None


def _build_search_args(topic: str) -> list[str]:
    return [CLI_BIN, "search", topic, "--json"]


def _coerce_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return [r for r in results if isinstance(r, dict)]
    return []


def _record_iso_date(rec: dict[str, Any]) -> str | None:
    value = rec.get("date")
    if isinstance(value, str) and _ISO_DATE_RE.match(value.strip()):
        return value.strip()
    return None


def _run_cli(cmd: list[str], timeout: int) -> dict[str, Any]:
    if not is_available():
        return {"results": [], "error": f"{CLI_BIN} not on PATH"}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        _log(f"Timeout: {exc}")
        return {"results": [], "error": str(exc)}
    except FileNotFoundError as exc:
        _log(f"Binary missing: {exc}")
        return {"results": [], "error": str(exc)}
    except OSError as exc:
        _log(f"Spawn failed: {exc}")
        return {"results": [], "error": str(exc)}

    if result.returncode != 0:
        snippet = (result.stderr or "").strip().splitlines()[:1]
        first = snippet[0] if snippet else f"exit {result.returncode}"
        _log(f"CLI exit {result.returncode}: {first}")
        return {"results": [], "error": first}

    stdout = result.stdout or ""
    if not stdout.strip():
        return {"results": []}
    if stdout.strip().startswith(_NO_RESULTS_PREFIX):
        return {"results": []}
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        _log(f"JSON decode failed: {exc}")
        return {"results": [], "error": f"json decode: {exc}"}

    return {"results": _coerce_list(data)}


def search_techmeme(
    topic: str,
    from_date: str,
    to_date: str,
    depth: Depth = "default",
) -> dict[str, Any]:
    """Search Techmeme's live archive via techmeme-pp-cli."""
    if not topic or not topic.strip():
        return {"results": []}
    if not is_available():
        return {"results": [], "error": f"{CLI_BIN} not on PATH"}
    limit = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    cmd = _build_search_args(topic)
    _log(f"search '{topic}' (cap={limit})")
    response = _run_cli(cmd, timeout=SEARCH_TIMEOUT)
    records = response.get("results") or []
    if isinstance(records, list):
        dated_in_window = []
        undated = []
        dropped = 0
        for rec in records:
            iso = _record_iso_date(rec)
            if iso is None:
                undated.append(rec)
            elif from_date <= iso <= to_date:
                dated_in_window.append(rec)
            else:
                dropped += 1
        if dropped:
            _log(f"dropped {dropped} records outside {from_date}..{to_date}")
        if records and not dated_in_window and not dropped:
            _log(
                "no records carry usable dates; date windowing inactive "
                "(old techmeme-pp-cli binary or upstream markup change)"
            )
        response["results"] = (dated_in_window + undated)[:limit]
    _log(f"found {len(response.get('results') or [])} records")
    return response


def _is_story_headline(headline: str, source: str) -> bool:
    if not headline or len(headline.split()) < MIN_HEADLINE_WORDS:
        return False
    return not (source and headline.strip().lower() == source.strip().lower())


def parse_techmeme_response(
    response: dict[str, Any],
    query: str = "",
) -> list[dict[str, Any]]:
    raw = response.get("results") if isinstance(response, dict) else None
    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    for i, rec in enumerate(raw):
        if not isinstance(rec, dict):
            continue
        headline = " ".join(str(rec.get("headline") or "").split()).strip()
        source_name = str(rec.get("source") or "").strip()
        if not _is_story_headline(headline, source_name):
            continue
        link = str(rec.get("link") or "").strip()
        if not link:
            continue

        rank_decay = max(0.3, 1.0 - (i * 0.03))
        content_score = token_overlap_relevance(query, headline) if query else 0.5
        relevance = min(1.0, 0.55 * rank_decay + 0.45 * content_score)

        items.append(
            {
                "id": link,
                "title": headline,
                "url": link,
                "source_name": source_name,
                "date": _record_iso_date(rec),
                "engagement": {},
                "relevance": round(relevance, 2),
                "why_relevant": (
                    f"Techmeme headline ({source_name})" if source_name else "Techmeme headline"
                ),
            }
        )

    return items


def format_techmeme_markdown(items: list[dict[str, Any]], query: str) -> str:
    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        source = item.get("source_name", "")
        date = item.get("date", "")
        lines = [
            f"{i}. **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**",
        ]
        meta = []
        if source:
            meta.append(source)
        if date:
            meta.append(date)
        if meta:
            lines.append(f"   {' • '.join(meta)}")
        return lines

    return format_results_markdown(items, query, "Techmeme", "headlines", _item_lines)


def techmeme_search_tool(
    query: str,
    max_results: int = 16,
    time_range: str | None = None,
    depth: Depth = "default",
    response_format: str = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Techmeme — free, no API key needed.

    Requires techmeme-pp-cli on PATH (install via:
    npx -y @mvanhorn/printing-press-library install techmeme --cli-only)
    """
    if not query or not query.strip():
        return ErrorResponse(
            error="Query cannot be empty", details="Provide a non-empty search query."
        )

    if not is_available():
        return ErrorResponse(
            error="Techmeme search unavailable",
            details=(
                "techmeme-pp-cli not found on PATH. Install with: "
                "npx -y @mvanhorn/printing-press-library install techmeme --cli-only"
            ),
        )

    from datetime import datetime, timedelta

    today = datetime.now().date()
    from_date = "2000-01-01"
    to_date = today.isoformat()

    if time_range:
        if time_range == "d":
            from_date = (today - timedelta(days=1)).isoformat()
        elif time_range == "w":
            from_date = (today - timedelta(weeks=1)).isoformat()
        elif time_range == "m":
            from_date = (today - timedelta(weeks=4)).isoformat()
        elif time_range == "y":
            from_date = (today - timedelta(weeks=52)).isoformat()

    depth_limits = _ALL_DEPTH_LIMITS.get("techmeme", {"quick": 8, "default": 16, "deep": 30})
    max_results = min(max_results, depth_limits.get(depth, 16))

    try:
        response = search_techmeme(query, from_date, to_date, depth)
        items = parse_techmeme_response(response, query)
        items = items[:max_results]

        if response_format == "markdown":
            return format_techmeme_markdown(items, query)

        from .._models import SearchResult, build_search_response

        results = []
        for item in items:
            body_parts = []
            if item.get("title"):
                body_parts.append(item["title"])
            if item.get("source_name"):
                body_parts.append(f"via {item['source_name']}")
            if item.get("date"):
                body_parts.append(item["date"])
            results.append(
                SearchResult(
                    title=item.get("title", "Techmeme headline"),
                    href=item.get("url", ""),
                    url=item.get("url", ""),
                    body=" ".join(body_parts) if body_parts else None,
                )
            )
        return build_search_response(results, query)

    except Exception as e:
        logger.exception("Techmeme search failed for query %r", query)
        return ErrorResponse(error="Techmeme search failed", details=str(e))
