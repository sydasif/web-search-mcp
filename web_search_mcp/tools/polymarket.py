"""Polymarket prediction market search via Gamma API (free, no auth required).

Uses gamma-api.polymarket.com for event/market discovery.
No API key needed - public read-only API with generous rate limits (15K req/10s).
"""

from __future__ import annotations

import contextlib
import logging
import math
import re
from typing import Any

from .._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from .._http import get_json_client
from .._models import ErrorResponse, SearchResponse
from .._models.types import Depth
from .._utils import format_results_markdown, token_overlap_relevance

logger = logging.getLogger(__name__)

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

DEPTH_CONFIG = _ALL_DEPTH_LIMITS.get("polymarket", {"quick": 1, "default": 3, "deep": 4})
RESULT_CAP = {"quick": 5, "default": 15, "deep": 25}

_LOW_SIGNAL_QUERY_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "of",
        "for",
        "and",
        "or",
        "to",
        "is",
        "are",
        "was",
        "were",
        "will",
        "be",
        "by",
        "with",
        "from",
        "as",
        "it",
        "its",
        "not",
        "no",
        "but",
        "if",
        "so",
        "do",
        "has",
        "had",
        "have",
        "this",
        "that",
        "what",
        "who",
    }
)

_NOISE_WORDS = frozenset(
    {
        "west",
        "east",
        "north",
        "south",
        "central",
        "southern",
        "northern",
        "eastern",
        "western",
        "champion",
        "championship",
        "league",
        "division",
        "conference",
        "cup",
        "series",
        "team",
        "game",
        "match",
        "season",
        "win",
        "winner",
        "finals",
        "club",
        "island",
        "city",
        "park",
        "hill",
        "lake",
        "bay",
        "beach",
        "valley",
        "river",
        "mountain",
        "county",
        "state",
        "village",
        "town",
        "point",
        "creek",
        "springs",
        "heights",
        "ridge",
        "bridge",
        "harbor",
        "port",
        "station",
        "center",
        "square",
        "field",
        "forest",
        "garden",
        "tower",
        "school",
        "church",
        "camp",
        "ranch",
        "crossing",
        "shore",
        "rock",
        "summit",
        "falls",
        "grove",
        "haven",
        "market",
        "odds",
        "prediction",
        "forecast",
        "chance",
        "probability",
        "vs",
        "versus",
    }
)

_DOMAIN_WORDS = frozenset(
    {
        "cli",
        "mcp",
        "protocol",
        "tool",
        "app",
        "code",
        "model",
        "ai",
        "api",
        "software",
        "plugin",
        "skill",
        "agent",
        "bot",
        "search",
        "research",
    }
)

_SWEEP_RESIDUE = frozenset(
    {
        "frontier",
        "developments",
        "development",
        "news",
        "trends",
        "trend",
        "latest",
        "industry",
        "space",
        "ecosystem",
        "landscape",
        "overview",
        "updates",
        "update",
        "future",
        "outlook",
        "sector",
        "field",
        "world",
    }
)

_NOISE_WORDS = _NOISE_WORDS | _DOMAIN_WORDS


def _log(msg: str) -> None:
    logger.debug("[Polymarket] %s", msg)


def _extract_core_subject(topic: str) -> str:
    topic = topic.strip()
    prefixes = [
        r"^last \d+ days?\s+",
        r"^what(?:'s| is| are) (?:people saying about|happening with|going on with)\s+",
        r"^how (?:is|are)\s+",
        r"^tell me about\s+",
        r"^research\s+",
    ]
    for pattern in prefixes:
        topic = re.sub(pattern, "", topic, flags=re.IGNORECASE)
    return topic.strip()


def _expand_queries(topic: str) -> list[str]:
    core = _extract_core_subject(topic)
    queries = [core]

    words = core.split()
    if len(words) >= 2:
        for word in words:
            if (
                len(word) > 1
                and word.lower() not in _LOW_SIGNAL_QUERY_TOKENS
                and word.lower() not in _NOISE_WORDS
            ):
                queries.append(word)

    if topic.lower().strip() != core.lower():
        queries.append(topic.strip())

    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique[:6]


_GENERIC_TAGS = frozenset({"sports", "politics", "crypto", "science", "culture", "pop culture"})


def _domain_stem(word: str) -> str | None:
    if word in _DOMAIN_WORDS:
        return word
    if word.endswith("ies") and len(word) > 4:
        stem = word[:-3] + "y"
        if stem in _DOMAIN_WORDS:
            return stem
    if len(word) > 3 and word.endswith("es") and word[:-2] in _DOMAIN_WORDS:
        return word[:-2]
    if len(word) > 2 and word.endswith("s") and word[:-1] in _DOMAIN_WORDS:
        return word[:-1]
    return None


def _informative_words(core_words: list[str]) -> list[str]:
    return [w for w in core_words if w not in _NOISE_WORDS and _domain_stem(w) is None]


def _domain_word_fallback_allows(
    core_words: list[str], informative: list[str], title_lower: str, title_words: set[str]
) -> bool:
    hard_informative = [w for w in informative if w not in _SWEEP_RESIDUE]
    if hard_informative:
        return False
    domain_stems = []
    seen: set[str] = set()
    for w in core_words:
        stem = _domain_stem(w)
        if stem and stem not in seen:
            seen.add(stem)
            domain_stems.append(stem)
    if not domain_stems:
        return False
    for word in domain_stems:
        if word in title_words or f"{word}s" in title_words or f"{word}es" in title_words:
            return True
        if len(word) >= 4 and word in title_lower:
            return True
    return False


def _acronym_credit(core_words: list[str], title_words: set[str]) -> int:
    informative_set = set(_informative_words(core_words))
    credit = 0
    run: list[str] = []
    for word in core_words + [""]:
        if word in informative_set:
            run.append(word)
            continue
        if len(run) >= 3:
            acronym = "".join(w[0] for w in run)
            if len(acronym) >= 3 and acronym in title_words:
                credit = max(credit, len(run))
        run = []
    return credit


def _passes_topic_filter(topic: str, event_title: str) -> bool:
    core = _extract_core_subject(topic).lower()
    core_words = [w for w in re.sub(r"[^\w\s]", " ", core).split() if len(w) > 1]

    if not core_words:
        return True

    informative = _informative_words(core_words)

    if not informative:
        return True

    title_lower = " ".join(re.sub(r"[^\w\s]", " ", event_title.lower()).split())
    title_words = set(title_lower.split())

    match_count = 0
    for word in informative:
        if word in title_words:
            match_count += 1
            continue
        if len(word) >= 4 and word in title_lower:
            match_count += 1

    if match_count < 2:
        match_count = max(match_count, _acronym_credit(core_words, title_words))

    min_match = 2 if len(informative) >= 3 else 1
    return match_count >= min_match


def _fetch_events_page(query: str, page: int, timeout: int = 15) -> dict[str, Any] | None:
    params = {"q": query, "page": str(page)}
    try:
        with get_json_client(timeout=timeout) as client:
            response = client.get(GAMMA_SEARCH_URL, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning("Polymarket search failed for query '%s' page %d: %s", query, page, e)
        return None


def search_polymarket(
    topic: str,
    from_date: str,
    to_date: str,
    depth: Depth = "default",
) -> dict[str, Any]:
    if not topic or not topic.strip():
        return {"results": []}

    queries = _expand_queries(topic)
    pages = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    all_events: list[dict[str, Any]] = []
    seen_ids: set = set()

    for query in queries:
        for page in range(pages):
            data = _fetch_events_page(query, page)
            if not data or not isinstance(data, dict):
                continue
            events = data.get("data") or data.get("events") or []
            if not isinstance(events, list):
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("id") or event.get("slug") or "")
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                all_events.append(event)

    _log(f"expanded {len(queries)} queries, fetched {len(all_events)} unique events")
    return {"results": all_events}


def _parse_event(event: dict[str, Any], query: str) -> dict[str, Any] | None:
    event_id = str(event.get("id") or event.get("slug") or "")
    if not event_id:
        return None

    title = str(event.get("title") or event.get("question") or "").strip()
    if not title:
        return None

    if not _passes_topic_filter(query, title):
        return None

    # Get end date for relevance
    end_date = event.get("endDate") or event.get("end_date") or ""
    date_str = None
    if end_date:
        with contextlib.suppress(Exception):
            date_str = end_date.split("T")[0]

    # Volume/liquidity as engagement signal
    volume: float = 0
    try:
        vol = event.get("volume") or event.get("volume24h") or event.get("volumeNum") or 0
        volume = float(vol) if vol else 0
    except (TypeError, ValueError):
        volume = 0

    liquidity: float = 0
    try:
        liq = event.get("liquidity") or event.get("liquidityNum") or 0
        liquidity = float(liq) if liq else 0
    except (TypeError, ValueError):
        liquidity = 0

    engagement_score = min(0.3, math.log10(volume + 1) / 20 + math.log10(liquidity + 1) / 20)

    # Markets within event
    markets = event.get("markets") or []
    outcomes = []
    for m in markets:
        if isinstance(m, dict):
            outcomes.append(str(m.get("question") or m.get("title") or ""))

    url = f"https://polymarket.com/event/{event_id}"

    content_score = token_overlap_relevance(query, title) if query else 0.5
    relevance = min(1.0, 0.7 * content_score + 0.3 * engagement_score)

    return {
        "id": event_id,
        "title": title,
        "url": url,
        "author": "",
        "date": date_str,
        "engagement": {
            "volume": volume,
            "liquidity": liquidity,
            "outcomes": outcomes,
        },
        "relevance": round(relevance, 2),
        "why_relevant": f"Polymarket event (${volume:,.0f} volume, ${liquidity:,.0f} liquidity)",
    }


def parse_polymarket_response(
    response: dict[str, Any],
    query: str = "",
) -> list[dict[str, Any]]:
    raw = response.get("results") if isinstance(response, dict) else None
    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    for event in raw:
        if not isinstance(event, dict):
            continue
        parsed = _parse_event(event, query)
        if parsed:
            items.append(parsed)

    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return items


def format_polymarket_markdown(items: list[dict[str, Any]], query: str) -> str:
    def _item_lines(item: dict[str, Any], i: int) -> list[str]:
        vol = item.get("engagement", {}).get("volume", 0)
        liq = item.get("engagement", {}).get("liquidity", 0)
        lines = [
            f"{i}. **[{item.get('title', 'Untitled')}]({item.get('url', '#')})**",
            f"   Volume: ${vol:,.0f} • Liquidity: ${liq:,.0f}",
        ]
        outcomes = item.get("engagement", {}).get("outcomes", [])
        if outcomes:
            lines.append(f"   Outcomes: {', '.join(outcomes[:3])}")
        if item.get("date"):
            lines.append(f"   Ends: {item['date']}")
        return lines

    return format_results_markdown(items, query, "Polymarket", "markets", _item_lines)


def polymarket_search_tool(
    query: str,
    max_results: int = 15,
    time_range: str | None = None,
    depth: Depth = "default",
    response_format: str = "markdown",
) -> str | SearchResponse | ErrorResponse:
    """Search Polymarket prediction markets — free, no API key needed."""
    if not query or not query.strip():
        return ErrorResponse(
            error="Query cannot be empty", details="Provide a non-empty search query."
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

    result_cap = RESULT_CAP.get(depth, RESULT_CAP["default"])
    max_results = min(max_results, result_cap)

    try:
        response = search_polymarket(query, from_date, to_date, depth)
        items = parse_polymarket_response(response, query)
        items = items[:max_results]

        if response_format == "markdown":
            return format_polymarket_markdown(items, query)

        from .._models import SearchResult, build_search_response

        results = []
        for item in items:
            body_parts = []
            if item.get("title"):
                body_parts.append(item["title"])
            if item.get("engagement", {}).get("volume"):
                vol = item["engagement"]["volume"]
                body_parts.append(f"Volume: ${vol:,.0f}")
            if item.get("engagement", {}).get("outcomes"):
                body_parts.append(f"Outcomes: {', '.join(item['engagement']['outcomes'][:3])}")
            results.append(
                SearchResult(
                    title=item.get("title", "Polymarket market"),
                    href=item.get("url", ""),
                    url=item.get("url", ""),
                    body=" ".join(body_parts) if body_parts else None,
                )
            )
        return build_search_response(results, query)

    except Exception as e:
        logger.exception("Polymarket search failed for query %r", query)
        return ErrorResponse(error="Polymarket search failed", details=str(e))
