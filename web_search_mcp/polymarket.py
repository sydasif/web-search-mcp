"""Polymarket prediction market search via Gamma API (free, no auth required).

Uses gamma-api.polymarket.com for event/market discovery.
No API key needed - public read-only API with generous rate limits.
"""

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("web-search-mcp")

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"

# Pages to fetch per query (API returns 5 events per page)
DEPTH_CONFIG = {"quick": 1, "default": 3, "deep": 4}
RESULT_CAP = {"quick": 5, "default": 15, "deep": 25}
MAX_WORKERS = 8
TIMEOUT = 15

_NOISE_WORDS = frozenset(
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


def _extract_core_subject(topic: str) -> str:
    """Strip common prefixes from topic string."""
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
    """Generate search queries to cast a wider net."""
    core = _extract_core_subject(topic)
    queries = [core]
    words = core.split()
    if len(words) >= 2:
        for word in words:
            if len(word) > 1 and word.lower() not in _NOISE_WORDS:
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


def _passes_topic_filter(topic: str, event_title: str) -> bool:
    """Check if event title contains enough informative words from the topic."""
    core = _extract_core_subject(topic).lower()
    core_words = [w for w in re.sub(r"[^\w\s]", " ", core).split() if len(w) > 1]
    if not core_words:
        return True

    informative = [w for w in core_words if w not in _NOISE_WORDS]
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

    min_matches = 2 if len(informative) >= 3 else 1
    return match_count >= min_matches


def _format_price_movement(market: dict) -> str | None:
    """Pick the most significant price change and format it."""
    changes = [
        (abs(market.get("oneDayPriceChange") or 0), market.get("oneDayPriceChange"), "today"),
        (abs(market.get("oneWeekPriceChange") or 0), market.get("oneWeekPriceChange"), "this week"),
        (
            abs(market.get("oneMonthPriceChange") or 0),
            market.get("oneMonthPriceChange"),
            "this month",
        ),
    ]
    changes.sort(key=lambda x: x[0], reverse=True)
    abs_change, raw_change, period = changes[0]
    if abs_change < 0.01:
        return None
    direction = "up" if raw_change > 0 else "down"
    pct = abs_change * 100
    return f"{direction} {pct:.1f}% {period}"


def _parse_outcome_prices(market: dict) -> list[tuple]:
    """Parse outcomePrices JSON string into list of (outcome_name, price) tuples."""
    outcomes_raw = market.get("outcomes") or []
    prices_raw = market.get("outcomePrices")
    if not prices_raw:
        return []
    try:
        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw)
        else:
            outcomes = outcomes_raw
    except (json.JSONDecodeError, TypeError):
        outcomes = []
    try:
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
    except (json.JSONDecodeError, TypeError):
        return []
    result = []
    for i, price in enumerate(prices):
        try:
            p = float(price)
        except (ValueError, TypeError):
            continue
        name = outcomes[i] if i < len(outcomes) else f"Outcome {i + 1}"
        result.append((name, p))
    return result


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(val or default)
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


def _search_single_query(query: str, page: int = 1) -> dict:
    """Run a single search query against Gamma API."""
    params = {
        "q": query,
        "page": str(page),
        "events_status": "active",
        "keep_closed_markets": "0",
    }
    url = f"{GAMMA_SEARCH_URL}?{urlencode(params)}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT, headers={"User-Agent": "web-search-mcp/1.0"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Polymarket search failed for '%s' page %d: %s", query, page, e)
        return {"events": [], "error": str(e)}


def search_polymarket(
    topic: str,
    from_date: str | None = None,
    to_date: str | None = None,
    depth: str = "default",
) -> list[dict]:
    """Search Polymarket via Gamma API with query expansion.

    Args:
        topic: Search topic
        from_date: Optional start date (YYYY-MM-DD)
        to_date: Optional end date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of normalized event dicts.
    """
    pages = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    cap = RESULT_CAP.get(depth, RESULT_CAP["default"])
    queries = _expand_queries(topic)
    logger.info("Polymarket searching '%s' with %d queries, pages=%d", topic, len(queries), pages)

    all_events: dict[str, tuple] = {}

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(queries) * pages)) as executor:
        futures = {}
        for i, q in enumerate(queries):
            for p in range(1, pages + 1):
                futures[executor.submit(_search_single_query, q, p)] = i
        for future in as_completed(futures):
            query_idx = futures[future]
            try:
                response = future.result(timeout=TIMEOUT)
                for event in response.get("events", []):
                    event_id = event.get("id", "")
                    if not event_id:
                        continue
                    if event_id not in all_events:
                        all_events[event_id] = (event, query_idx)
                    elif query_idx < all_events[event_id][1]:
                        all_events[event_id] = (event, query_idx)
            except Exception as e:
                logger.warning("Polymarket query future failed: %s", e)

    merged_events = [ev for ev, _ in sorted(all_events.values(), key=lambda x: x[1])]
    logger.info("Polymarket found %d unique events", len(merged_events))

    return _parse_events(merged_events, topic, cap)


# ─────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────


def _parse_events(events: list[dict], topic: str, cap: int) -> list[dict]:
    """Parse Gamma API events into normalized item dicts."""
    items = []
    for i, event in enumerate(events):
        title = event.get("title", "")
        slug = event.get("slug", "")
        if event.get("closed", False):
            continue
        if not event.get("active", True):
            continue
        if topic and not _passes_topic_filter(topic, title):
            continue

        markets = event.get("markets", [])
        if not markets:
            continue
        active_markets = []
        for m in markets:
            if m.get("closed", False):
                continue
            if not m.get("active", True):
                continue
            try:
                liq = float(m.get("liquidity", 0) or 0)
            except (ValueError, TypeError):
                liq = 0
            if liq > 0:
                active_markets.append(m)
        if not active_markets:
            continue

        active_markets.sort(key=lambda m: _safe_float(m.get("volume", 0)), reverse=True)
        top_market = active_markets[0]

        outcome_prices = _parse_outcome_prices(top_market)

        # Synthesize outcomes from sub-markets for neg-risk binary markets
        top_outcomes_are_binary = len(outcome_prices) == 2 and {
            n.lower() for n, _ in outcome_prices
        } == {"yes", "no"}
        if top_outcomes_are_binary and len(active_markets) > 1:
            synth_outcomes = []
            for m in active_markets:
                q = m.get("question", "")
                if not q:
                    continue
                pairs = _parse_outcome_prices(m)
                yes_price = next((p for name, p in pairs if name.lower() == "yes"), None)
                if yes_price is not None and yes_price > 0.005:
                    # Shorten question to just the subject
                    short = q.strip().rstrip("?")
                    m2 = re.match(
                        r"^Will\s+(.+?)\s+(?:win|be|make|reach|have|lose|qualify|advance|strike|agree|pass|sign|get|become|remain|stay|leave|survive|next)\b",
                        short,
                        re.IGNORECASE,
                    )
                    if m2:
                        short = m2.group(1).strip()
                    elif len(short) > 40:
                        short = short[:40]
                    synth_outcomes.append((short, yes_price))
            if synth_outcomes:
                synth_outcomes.sort(key=lambda x: x[1], reverse=True)
                outcome_prices = synth_outcomes

        price_movement = _format_price_movement(top_market)
        event_volume1mo = _safe_float(event.get("volume1mo"))
        event_liquidity = _safe_float(event.get("liquidity"))
        volume24hr = _safe_float(event.get("volume24hr")) or _safe_float(
            top_market.get("volume24hr")
        )
        liquidity = event_liquidity or _safe_float(top_market.get("liquidity"))
        url = (
            f"https://polymarket.com/event/{slug}"
            if slug
            else f"https://polymarket.com/event/{event.get('id', '')}"
        )

        # Relevance scoring
        core = _extract_core_subject(topic).lower() if topic else ""
        title_lower = title.lower()
        if core and core in title_lower:
            text_score = 1.0
        elif core:
            q_tokens = set(core.split())
            t_tokens = set(title_lower.split())
            overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
            text_score = min(1.0, overlap * 2)
        else:
            text_score = 0.5

        vol_raw = event_volume1mo or volume24hr
        vol_score = min(1.0, math.log1p(vol_raw) / 16)
        liq_score = min(1.0, math.log1p(liquidity) / 14)
        market_quality = 0.50 * vol_score + 0.25 * liq_score
        relevance = min(1.0, text_score * (0.75 + 0.25 * market_quality))

        top_outcomes = outcome_prices[:3]
        remaining = max(0, len(outcome_prices) - 3)

        items.append(
            {
                "event_id": event.get("id", ""),
                "title": title,
                "question": top_market.get("question", title),
                "url": url,
                "outcome_prices": top_outcomes,
                "outcomes_remaining": remaining,
                "price_movement": price_movement,
                "volume24hr": volume24hr,
                "volume1mo": event_volume1mo,
                "liquidity": liquidity,
                "date": (event.get("updatedAt") or "")[:10] or None,
                "relevance": round(relevance, 2),
                "why_relevant": f"Prediction market: {title[:60]}",
            }
        )

    items.sort(key=lambda x: x["relevance"], reverse=True)

    # Drop all results if nothing genuinely on-topic
    if items and items[0]["relevance"] < 0.15:
        logger.info("Polymarket: all results below relevance threshold, dropping")
        return []

    return items[:cap]
