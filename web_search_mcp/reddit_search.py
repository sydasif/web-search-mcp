"""Keyless Reddit pipeline: tiered free search + comment enrichment.

Replaces the dead ``.json`` free path. Discovery tiers, cheapest/most-likely
first; enrichment then runs on whatever was discovered:

  Tier 0  one-shot legacy ``.json`` search — demoted. Datacenter IPs get 403,
          but a residential machine (where the skill usually runs) may still
          get 200, so it is worth one cheap try. Honors the "brute-force .json"
          intent without depending on it.
  Tier 1  RSS discovery (reddit_rss) — keyless, robust, the load-bearing path.
  Tier 2  shreddit comment + count enrichment (reddit_shreddit) for top posts.

Returns ``[]`` (never raises) so the caller can fall through to other sources
when every keyless tier comes up empty.
"""

import concurrent.futures
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from . import reddit_rss, reddit_shreddit, reddit_listing

ENRICH_LIMITS = reddit_shreddit.ENRICH_LIMITS
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
    }
)


# ── Query expansion (ported from last30days-skill reddit.py) ─────────────


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
        r"\b(how to|tutorial|guide|setup|install|configure|troubleshoot|error|fix|debug)\b", text
    ):
        return "how_to"
    if re.search(r"\b(thoughts on|worth it|should i|opinion|review)\b", text):
        return "opinion"
    if re.search(r"\b(pricing|feature|features|best .* for)\b", text):
        return "product"
    if re.search(r"\b(predict|prediction|odds|forecast|chance)\b", text):
        return "prediction"
    return "general"


def expand_queries(topic: str, depth: str) -> List[str]:
    """Generate 1-4 query variants from topic based on intent and depth.

    Ported from last30days-skill reddit.py expand_reddit_queries().
    Uses local logic (no LLM call needed):
    1. Extract core subject (strip noise words)
    2. Include original topic if different from core
    3. For default/deep: add casual/review variant
    4. For deep: add problem/issues variant

    Returns 1-4 query strings depending on depth.
    """
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
    seen: set = set()
    unique: List[str] = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def _log(msg: str) -> None:
    sys.stderr.write(f"[RedditKeyless] {msg}\n")
    sys.stderr.flush()


def _tier0_json(topic: str, depth: str) -> List[Dict[str, Any]]:
    """One cheap global ``.json`` discovery attempt. Returns [] on the 403 wall."""
    try:
        from . import reddit_public

        return reddit_public.search(topic, depth=depth) or []
    except Exception as e:  # never let the demoted tier sink the run
        _log(f"Tier 0 (.json) unavailable: {e}")
        return []


def _top_subreddits(posts: List[Dict[str, Any]], limit: int = MAX_DERIVED_SUBS) -> List[str]:
    """Most frequent subreddits across discovered posts (for score backfill)."""
    counts = Counter(p.get("subreddit", "") for p in posts if p.get("subreddit"))
    return [sub for sub, _ in counts.most_common(limit)]


def _apply_scores(post: Dict[str, Any], scored: Dict[str, int]) -> None:
    post["score"] = scored["score"]
    post["num_comments"] = scored["num_comments"]
    post.setdefault("engagement", {})["score"] = scored["score"]
    post["engagement"]["num_comments"] = scored["num_comments"]


def _discover(topic: str, depth: str, subreddits: Optional[List[str]]) -> List[Dict[str, Any]]:
    # Tier 0: demoted one-shot .json (dead for normal users too, but free to try).
    posts = _tier0_json(topic, depth)
    if posts:
        _log(f"Tier 0 (.json) returned {len(posts)} posts")
        return posts

    # Tier 1: keyless discovery. RSS gives breadth (incl. global keyword search);
    # the listing partials give real upvote scores.
    rss_posts = reddit_rss.search_rss(topic, depth=depth, subreddits=subreddits)

    if subreddits:
        # Targeted run: the caller chose these subreddits, so their listing cards
        # are on-topic — include them as scored discovery AND as a score source.
        listing_posts = reddit_listing.fetch_listings(subreddits, depth=depth, query=topic)
        score_source = listing_posts
    else:
        # Bare global run: subreddits derived from noisy RSS results are NOT
        # reliably on-topic, so their listings are used ONLY to backfill scores
        # onto the keyword-matched RSS posts — never merged as discovery, which
        # would flood results with high-upvote but irrelevant posts.
        listing_posts = []
        derived = _top_subreddits(rss_posts)
        score_source = reddit_listing.fetch_listings(derived, depth=depth, query=topic)
    _log(
        f"Tier 1 (RSS) {len(rss_posts)} posts; "
        f"{'listing discovery ' + str(len(listing_posts)) if subreddits else 'score-only'}; "
        f"{len(score_source)} scored cards"
    )

    # Score lookup by post id, from the scored listing cards.
    score_map: Dict[str, Dict[str, int]] = {}
    for p in score_source:
        pid = p.get("metadata", {}).get("post_id", "")
        if pid:
            score_map[pid] = {"score": p["score"], "num_comments": p["num_comments"]}

    # Merge: scored listing posts first (targeted only), then RSS breadth,
    # backfilled with real scores where the post appears in a listing.
    merged: List[Dict[str, Any]] = []
    seen: set = set()
    for p in listing_posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            merged.append(p)
    for p in rss_posts:
        if p["url"] in seen:
            continue
        pid = reddit_listing._post_id(p["url"])
        if pid in score_map:
            _apply_scores(p, score_map[pid])
        seen.add(p["url"])
        merged.append(p)
    return merged


def _enrich_one(post: Dict[str, Any]) -> Dict[str, Any]:
    """Attach shreddit comments + real comment count. Never raises."""
    try:
        data = reddit_shreddit.fetch_comments(post.get("url", ""))
        if data.get("top_comments"):
            post["top_comments"] = data["top_comments"]
        if data.get("comment_insights"):
            post["comment_insights"] = data["comment_insights"]
        num = data.get("num_comments")
        if num is not None:
            post["num_comments"] = num
            post.setdefault("engagement", {})["num_comments"] = num
    except Exception:
        pass  # keep the post with whatever discovery gave us
    return post


def _enrich(posts: List[Dict[str, Any]], depth: str) -> List[Dict[str, Any]]:
    """Enrich the top N posts with comments under a total time budget."""
    limit = ENRICH_LIMITS.get(depth, ENRICH_LIMITS["default"])
    to_enrich = posts[:limit]
    rest = posts[limit:]
    if not to_enrich:
        return posts

    result_map: Dict[int, Dict[str, Any]] = {}
    try:
        with ThreadPoolExecutor(max_workers=min(limit, MAX_ENRICH_WORKERS)) as executor:
            futures = {executor.submit(_enrich_one, post): i for i, post in enumerate(to_enrich)}
            done, not_done = concurrent.futures.wait(futures, timeout=ENRICH_BUDGET)
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


def _slot_priority(topic: str, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order posts for enrichment slots: higher score first.

    Simplified version that just preserves the score-first sort order.
    The relevance-aware slot allocation from last30days-skill is omitted
    for simplicity in this initial integration.
    """
    return posts


def _run_single_pipeline(
    query: str,
    from_date: str,
    to_date: str,
    depth: str,
    subreddits: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Run the full pipeline for a single query variant. Never raises."""
    try:
        posts = _discover(query, depth, subreddits)
        if not posts:
            return []
        return [p for p in posts if p.get("date") is None or (from_date <= p["date"] <= to_date)]
    except Exception as e:
        _log(f"pipeline failed for query {query!r}: {e}")
        return []


def _merge_dedupe(post_batches: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Merge multiple post batches, deduping by URL (first occurrence wins)."""
    seen: set = set()
    merged: List[Dict[str, Any]] = []
    for batch in post_batches:
        for post in batch:
            url = post.get("url", "")
            if url and url not in seen:
                seen.add(url)
                merged.append(post)
    return merged


def search_and_enrich(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    subreddits: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Full keyless Reddit pipeline with query expansion + parallel fan-out.

    Generates 1-4 query variants from the topic, runs them concurrently
    (max 2 workers), merges and dedupes results, then enriches top posts
    with comment data via shreddit.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'
        subreddits: Optional pre-resolved subreddit names (without r/)

    Returns:
        List of normalized item dicts with top_comments/comment_insights
        attached on enriched posts. Capped by depth limit.
        Empty list when all keyless tiers fail.
    """
    queries = expand_queries(topic, depth)
    _log(f"expanded {len(queries)} queries: {queries}")

    if len(queries) == 1:
        posts = _run_single_pipeline(queries[0], from_date, to_date, depth, subreddits)
    else:
        workers = min(len(queries), MAX_FANOUT_WORKERS)
        batches: List[List[Dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_single_pipeline, q, from_date, to_date, depth, subreddits): q
                for q in queries
            }
            # Wait with timeout to prevent indefinite blocking on stuck threads.
            done, not_done = concurrent.futures.wait(futures, timeout=ENRICH_BUDGET)
            for future in not_done:
                q = futures[future]
                _log(f"fan-out timed out for {q!r}")
                future.cancel()
            for future in done:
                q = futures[future]
                try:
                    batches.append(future.result(timeout=0))
                except Exception as e:
                    _log(f"fan-out failed for {q!r}: {e}")
        posts = _merge_dedupe(batches)

    if not posts:
        return []

    # Rank by real upvote score, then relevance, then recency.
    posts.sort(
        key=lambda p: (
            p.get("engagement", {}).get("score", 0) or 0,
            p.get("relevance", 0) or 0,
            p.get("date") or "",
        ),
        reverse=True,
    )

    # Enrich top posts with shreddit comments.
    posts = _enrich(_slot_priority(topic, posts), depth)

    for i, post in enumerate(posts):
        post["id"] = f"R{i + 1}"

    # Cap results by depth limit
    depth_limits = {"quick": 10, "default": 25, "deep": 50}
    return posts[: depth_limits.get(depth, depth_limits["default"])]
