"""Keyless Reddit listing card fetch — scores posts via public HTML pages.

Reddit's subreddit listing pages (e.g. /r/python/top/?t=month) embed post
cards with upvote scores in data attributes. This module fetches those pages
and extracts scores to backfill RSS-discovered posts. No API key required.
"""

import html as _html
import logging
import re
from datetime import datetime, timezone
from typing import Any

from . import client
from ..utils import token_overlap_relevance

logger = logging.getLogger(__name__)

# Listing sorts pulled per subreddit (in addition to search), for volume.
LISTING_SORTS = {
    "quick": ["top"],
    "default": ["top", "hot"],
    "deep": ["top", "hot", "new"],
}

MAX_WORKERS = 3
FEED_TIMEOUT = 15


def _iso_to_date(value: str | None) -> str | None:
    """Parse an ISO-8601 timestamp to YYYY-MM-DD."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return None


def _iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _post_id(url: str) -> str:
    """Extract post ID from Reddit URL."""
    m = re.search(r"/comments/([A-Za-z0-9]+)", url or "")
    return m.group(1) if m else ""


def _parse_listing(html_text: str, subreddit: str, query: str) -> list[dict[str, Any]]:
    """Parse a listing page HTML into post dicts with real scores. Never raises."""
    if not html_text:
        return []

    posts: list[dict[str, Any]] = []

    # Reddit listing page structure: each post is in a shreddit-post element
    # with data attributes for score, comment count, etc.
    shreddit_pattern = re.compile(r"<shreddit-post[^>]*>")
    for m in shreddit_pattern.finditer(html_text):
        tag = m.group(0)

        # Extract attributes
        post_id = re.search(r'post-id="([^"]*)"', tag)
        title_match = re.search(r'title="([^"]*)"', tag)
        score_match = re.search(r'score="([^"]*)"', tag)
        comments_match = re.search(r'comment-count="([^"]*)"', tag)
        author_match = re.search(r'author="([^"]*)"', tag)
        permalink_match = re.search(r'permalink="([^"]*)"', tag)
        created_match = re.search(r'created-timestamp="([^"]*)"', tag)

        pid = post_id.group(1) if post_id else ""
        if not pid:
            continue

        title = _html.unescape(title_match.group(1)) if title_match else ""
        try:
            score = int(score_match.group(1)) if score_match else 0
        except (ValueError, TypeError):
            score = 0
        try:
            num_comments = int(comments_match.group(1)) if comments_match else 0
        except (ValueError, TypeError):
            num_comments = 0
        author = author_match.group(1) if author_match else "[deleted]"
        permalink = permalink_match.group(1) if permalink_match else ""
        created = created_match.group(1) if created_match else ""

        url = f"https://www.reddit.com{permalink}" if permalink else ""

        relevance = round(token_overlap_relevance(query, title), 3) if query else 0.0

        posts.append(
            {
                "id": "",
                "title": title,
                "url": url,
                "score": score,
                "num_comments": num_comments,
                "subreddit": subreddit,
                "created_utc": _iso_to_epoch(created),
                "author": author,
                "selftext": "",
                "date": _iso_to_date(created),
                "engagement": {
                    "score": score,
                    "num_comments": num_comments,
                    "upvote_ratio": None,
                },
                "relevance": relevance,
                "why_relevant": "Reddit Listing",
                "metadata": {"post_id": pid},
            }
        )

    return posts


def _fetch_listing(subreddit: str, sort: str, depth: str, query: str) -> list[dict[str, Any]]:
    """Fetch and parse one listing page. Never raises."""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}/?t=month"
        text = client.get_text(url, timeout=FEED_TIMEOUT, accept="text/html")
        return _parse_listing(text, subreddit, query) if text else []
    except Exception as e:
        logger.debug("listing fetch failed for r/%s/%s: %s", subreddit, sort, e)
        return []


def fetch_listings(
    subreddits: list[str],
    depth: str = "default",
    query: str = "",
) -> list[dict[str, Any]]:
    """Fetch listing cards for multiple subreddits to backfill scores.

    Args:
        subreddits: Subreddit names (without r/)
        depth: 'quick', 'default', or 'deep' — controls sorts fetched
        query: Query for relevance scoring

    Returns:
        List of post dicts with real scores from listing pages.
    """
    sorts = LISTING_SORTS.get(depth, LISTING_SORTS["default"])

    all_posts: list[dict[str, Any]] = []
    from concurrent.futures import ThreadPoolExecutor

    tasks = []
    for sub in subreddits:
        for sort in sorts:
            tasks.append((sub, sort))

    workers = min(MAX_WORKERS, len(tasks)) or 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_fetch_listing, sub, sort, depth, query): (sub, sort)
            for sub, sort in tasks
        }
        for future in futures:
            try:
                all_posts.extend(future.result(timeout=FEED_TIMEOUT + 5))
            except Exception as e:
                sub, sort = futures[future]
                logger.debug("listing future failed for r/%s/%s: %s", sub, sort, e)

    # Dedupe by post_id in metadata
    seen: set = set()
    unique: list[dict[str, Any]] = []
    for post in all_posts:
        pid = post.get("metadata", {}).get("post_id", "")
        if pid and pid not in seen:
            seen.add(pid)
            unique.append(post)

    for i, post in enumerate(unique):
        post["id"] = f"L{i + 1}"

    return unique
