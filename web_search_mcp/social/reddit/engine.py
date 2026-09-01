"""Keyless Reddit pipeline: tiered free search + comment enrichment."""

from __future__ import annotations

import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from ..._config import DEPTH_LIMITS as _ALL_DEPTH_LIMITS
from ..._models.types import Depth
from . import client, models, parsers
from ._utils import assign_ids, dedupe_by

logger = logging.getLogger(__name__)

ENRICH_LIMITS = parsers.ENRICH_LIMITS
ENRICH_BUDGET = 45  # seconds total across all enrichment threads
MAX_ENRICH_WORKERS = 4
MAX_DERIVED_SUBS = 5  # subreddits derived from RSS results for score backfill
MAX_FANOUT_WORKERS = 2  # conservative: parallel query fan-out

# ── Noise words for query expansion ──────────────────────────────────────
_PREFIXES = [
    "what are the best",
    "what is the best",
    "what are the latest",
    "what are people saying about",
    "what do people think about",
    "how do i use",
    "how to use",
    "how to",
    "what are",
    "what is",
    "tips for",
    "best practices for",
]
_NOISE_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "of",
        "in",
        "on",
        "for",
        "with",
        "about",
        "to",
        "how",
        "what",
        "which",
        "who",
        "why",
        "when",
        "where",
        "does",
        "should",
        "could",
        "would",
        "best",
        "top",
        "good",
        "great",
        "awesome",
        "killer",
        "latest",
        "new",
        "news",
        "update",
        "updates",
        "trending",
        "hottest",
        "popular",
        "practices",
        "features",
        "guide",
        "tutorial",
        "recommendations",
        "advice",
        "review",
        "reviews",
        "tips",
        "tricks",
        "methods",
        "strategies",
        "approaches",
        "using",
        "uses",
        "use",
        "people",
        "saying",
        "think",
        "said",
        "lately",
    },
)


# ── Query expansion ───────────────────────────────────────────────────────


def _extract_core_subject(topic: str) -> str:
    """Strip meta/research words to keep only the core subject."""
    text = topic.lower().strip().rstrip("?!.")
    # Strip prefixes
    for p in _PREFIXES:
        if text.startswith(p + " "):
            text = text[len(p) :].strip()
            break
    # Filter noise words
    words = text.split()
    filtered = [w for w in words if w not in _NOISE_WORDS]
    return " ".join(filtered) if filtered else text


def _infer_query_intent(topic: str) -> str:
    """Detect intent from topic keywords."""
    text = topic.lower().strip()
    if re.search(r"\b(vs|versus|compare|difference between)\b", text):
        return "comparison"
    if re.search(
        r"\b(how to|tutorial|guide|setup|install|configure|troubleshoot|error|fix|debug)\b",
        text,
    ):
        return "how_to"
    if re.search(r"\b(thoughts on|worth it|should i|opinion|review)\b", text):
        return "opinion"
    if re.search(r"\b(pricing|feature|features|best .* for)\b", text):
        return "product"
    if re.search(r"\b(predict|prediction|odds|forecast|chance)\b", text):
        return "prediction"
    return "general"


def expand_queries(topic: str, depth: Depth) -> list[str]:
    """Generate 1-4 query variants from topic based on intent and depth."""
    core = _extract_core_subject(topic)
    queries = [core] if core else [topic.strip()]

    original_clean = topic.strip().rstrip("?!.")
    if core.lower() != original_clean.lower() and len(original_clean.split()) <= 8:
        queries.append(original_clean)

    qtype = _infer_query_intent(topic)

    if qtype == "product":
        queries.append(f"{core} review OR recommendation OR best")

    if qtype == "comparison":
        queries.append(f"{core} worth it OR vs OR compared")

    if depth in ("default", "deep") and qtype in ("product", "opinion"):
        queries.append(f"{core} worth it OR thoughts OR review")

    if depth == "deep" and qtype in ("product", "opinion", "how_to"):
        queries.append(f"{core} issues OR problems OR bug OR broken")

    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def _tier0_json(topic: str, depth: Depth) -> list[dict[str, Any]]:
    """One cheap global ``.json`` discovery attempt. Returns [] on the 403 wall."""
    try:
        return client.search_json(topic, depth=depth) or []
    except Exception as e:  # never let the demoted tier sink the run
        logger.debug("Tier 0 (.json) unavailable: %s", e)
        return []


def _top_subreddits(posts: list[dict[str, Any]], limit: int = MAX_DERIVED_SUBS) -> list[str]:
    """Most frequent subreddits across discovered posts (for score backfill)."""
    counts = Counter(p.get("subreddit", "") for p in posts if p.get("subreddit"))
    return [sub for sub, _ in counts.most_common(limit)]


def _apply_scores(post: dict[str, Any], scored: dict[str, int]) -> None:
    post["score"] = scored.get("score", 0)
    post["num_comments"] = scored.get("num_comments", 0)
    post.setdefault("engagement", {})["score"] = scored.get("score", 0)
    post["engagement"]["num_comments"] = scored.get("num_comments", 0)


def _discover(topic: str, depth: Depth, subreddits: list[str] | None) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    if not subreddits:
        posts = _tier0_json(topic, depth)
    if posts:
        logger.debug("Tier 0 (.json) returned %d posts", len(posts))
        return posts

    if subreddits:
        rss_posts = []
        listing_posts = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            rss_future = executor.submit(
                parsers.search_rss,
                topic,
                depth=depth,
                subreddits=subreddits,
            )
            listing_future = executor.submit(
                models.fetch_listings,
                subreddits,
                depth=depth,
                query=topic,
            )
            rss_posts = rss_future.result() or []
            listing_posts = listing_future.result() or []
        score_source = listing_posts
    else:
        rss_posts = parsers.search_rss(topic, depth=depth, subreddits=None)
        listing_posts = []
        derived = _top_subreddits(rss_posts)
        score_source = models.fetch_listings(derived, depth=depth, query=topic)
    logger.debug(
        "Tier 1 (RSS) %d posts; %s; %d scored cards",
        len(rss_posts),
        f"listing discovery {len(listing_posts)}" if subreddits else "score-only",
        len(score_source),
    )

    score_map: dict[str, dict[str, int]] = {}
    for p in score_source:
        pid = p.get("metadata", {}).get("post_id", "")
        if pid:
            score_map[pid] = {"score": p["score"], "num_comments": p["num_comments"]}

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in listing_posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            merged.append(p)
    for p in rss_posts:
        if p["url"] in seen:
            continue
        pid = models._post_id(p["url"])
        if pid in score_map:
            _apply_scores(p, score_map[pid])
        seen.add(p["url"])
        merged.append(p)
    return merged


def _enrich_one(post: dict[str, Any]) -> dict[str, Any]:
    """Attach shreddit comments + real comment count. Never raises."""
    try:
        data = parsers.fetch_comments(post.get("url", ""))
        if data.get("top_comments"):
            post["top_comments"] = data["top_comments"]
        if data.get("comment_insights"):
            post["comment_insights"] = data["comment_insights"]
        num = data.get("num_comments")
        if num is not None:
            post["num_comments"] = num
            post.setdefault("engagement", {})["num_comments"] = num
    except Exception as e:
        logger.debug("enrichment failed for %s: %s", post.get("url", ""), e)
    return post


def _enrich(posts: list[dict[str, Any]], depth: Depth) -> list[dict[str, Any]]:
    """Enrich the top N posts with comments under a total time budget."""
    limit = ENRICH_LIMITS.get(depth, ENRICH_LIMITS["default"])
    to_enrich = posts[:limit]
    rest = posts[limit:]
    if not to_enrich:
        return posts

    result_map: dict[int, dict[str, Any]] = {}
    try:
        with ThreadPoolExecutor(max_workers=min(limit, MAX_ENRICH_WORKERS)) as executor:
            futures = {executor.submit(_enrich_one, post): i for i, post in enumerate(to_enrich)}
            done, not_done = wait(futures, timeout=ENRICH_BUDGET)
            for future in done:
                idx = futures[future]
                try:
                    result_map[idx] = future.result(timeout=0)
                except Exception:
                    result_map[idx] = to_enrich[idx]
            for future in not_done:
                idx = futures[future]
                result_map[idx] = to_enrich[idx]
                future.cancel()
        enriched = [result_map[i] for i in range(len(to_enrich))]
    except Exception:
        enriched = to_enrich

    return enriched + rest


def _run_single_pipeline(
    query: str,
    from_date: str,
    to_date: str,
    depth: Depth,
    subreddits: list[str] | None,
) -> list[dict[str, Any]]:
    """Run the full pipeline for a single query variant. Never raises."""
    try:
        posts = _discover(query, depth, subreddits)
        if not posts:
            return []
        return [p for p in posts if p.get("date") is None or (from_date <= p["date"] <= to_date)]
    except Exception as e:
        logger.debug("pipeline failed for query %r: %s", query, e)
        return []


def _merge_dedupe(post_batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge multiple post batches, deduping by URL (first occurrence wins)."""
    return dedupe_by([p for batch in post_batches for p in batch])


def search_and_enrich(
    topic: str,
    from_date: str,
    to_date: str,
    depth: Depth = "default",
    subreddits: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Full keyless Reddit pipeline with query expansion + parallel fan-out."""
    queries = expand_queries(topic, depth)
    logger.debug("expanded %d queries: %s", len(queries), queries)

    if len(queries) == 1:
        posts = _run_single_pipeline(queries[0], from_date, to_date, depth, subreddits)
    else:
        workers = min(len(queries), MAX_FANOUT_WORKERS)
        batches: list[list[dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_single_pipeline, q, from_date, to_date, depth, subreddits): q
                for q in queries
            }
            done, not_done = wait(futures, timeout=ENRICH_BUDGET)
            for future in not_done:
                q = futures[future]
                logger.debug("fan-out timed out for %r", q)
                future.cancel()
            for future in done:
                q = futures[future]
                try:
                    batches.append(future.result(timeout=0))
                except Exception as e:
                    logger.debug("fan-out failed for %r: %s", q, e)
        posts = _merge_dedupe(batches)

    if not posts:
        return []

    posts.sort(
        key=lambda p: (
            p.get("engagement", {}).get("score", 0) or 0,
            p.get("relevance", 0) or 0,
            p.get("date") or "",
        ),
        reverse=True,
    )

    posts = _enrich(posts, depth)

    assign_ids(posts, "R")

    depth_limits = _ALL_DEPTH_LIMITS["reddit"]
    return posts[: depth_limits.get(depth, depth_limits["default"])]
