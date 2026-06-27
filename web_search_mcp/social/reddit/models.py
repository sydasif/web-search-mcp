"""Keyless Reddit listing card fetch — scores posts via shreddit SVC endpoint.

Uses the SVC partial endpoint (``/svc/shreddit/community-more-posts/``) which
serves fully server-rendered ``<shreddit-post>`` HTML elements with real score,
comment count, and subreddit data. Unlike new Reddit's public HTML pages (which
are JS-rendered shells ~8 KB), the SVC endpoint returns rich server HTML with
real upvote scores.

This is the source repo's approach (mvanhorn/last30days-skill) and provides more
data (876 KB vs 365 KB) than old.reddit.com's <div class="thing"> structure.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..._models.types import Depth
from ..._utils import iso_to_date, iso_to_epoch, token_overlap_relevance
from . import client
from ._utils import extract_attr
from .parsers import LISTING_SORTS

logger = logging.getLogger(__name__)

MAX_WORKERS = 3
SVC_TIMEOUT = 15

# Match <shreddit-post> custom elements (same pattern as the original parser)
_SHREDDIT_POST = re.compile(r"<shreddit-post(?=[\s>])[^>]*>")


def _post_id(url: str) -> str:
    """Extract post ID from Reddit URL."""
    m = re.search(r"/comments/([A-Za-z0-9]+)", url or "")
    return m.group(1) if m else ""


def parse_cards(html_text: str, query: str = "") -> list[dict[str, Any]]:
    """Parse ``<shreddit-post>`` cards from the SVC endpoint into post dicts.

    The SVC endpoint returns ``<shreddit-post>`` elements with these attributes:
    - ``score``, ``comment-count`` — real upvote/comment numbers
    - ``post-title`` — the post title (not ``title`` like other endpoints)
    - ``subreddit-name`` — subreddit name (not ``subreddit``)
    - ``permalink``, ``author``, ``created-timestamp`` — same as other endpoints
    - No ``post-id`` attribute — extracted from the permalink instead
    """
    if not html_text:
        return []

    posts: list[dict[str, Any]] = []

    for m in _SHREDDIT_POST.finditer(html_text):
        tag = m.group(0)

        # Get permalink first — needed for post ID and URL
        permalink = extract_attr(tag, "permalink") or ""
        if "/comments/" not in permalink:
            continue

        # Extract post ID from permalink
        pid = _post_id(permalink)
        if not pid:
            continue

        # Score and comment count (same attributes as other endpoints)
        try:
            score = int(extract_attr(tag, "score") or 0)
        except (ValueError, TypeError):
            score = 0
        try:
            num_comments = int(extract_attr(tag, "comment-count") or 0)
        except (ValueError, TypeError):
            num_comments = 0

        # Title: SVC endpoint uses ``post-title`` instead of ``title``
        title = extract_attr(tag, "post-title") or extract_attr(tag, "title") or ""

        # Author
        author = extract_attr(tag, "author") or "[deleted]"

        # Subreddit: SVC has ``subreddit-name`` attribute
        subreddit = extract_attr(tag, "subreddit-name") or ""

        # Created timestamp (ISO-8601)
        created = extract_attr(tag, "created-timestamp")

        # Build URL
        url = f"https://www.reddit.com{permalink}" if permalink else ""

        relevance = token_overlap_relevance(query, title)

        posts.append(
            {
                "id": "",
                "title": title,
                "url": url,
                "score": score,
                "num_comments": num_comments,
                "subreddit": subreddit,
                "created_utc": iso_to_epoch(created),
                "author": author,
                "selftext": "",
                "date": iso_to_date(created),
                "engagement": {
                    "score": score,
                    "num_comments": num_comments,
                    "upvote_ratio": None,
                },
                "relevance": relevance,
                "why_relevant": "Reddit listing (SVC)",
                "metadata": {"post_id": pid},
            },
        )

    return posts


def _svc_url(subreddit: str, sort: str) -> str:
    """Build the SVC community-more-posts URL for a subreddit + sort."""
    sub = subreddit.removeprefix("r/").strip()
    url = f"https://www.reddit.com/svc/shreddit/community-more-posts/{sort}/?name={sub}"
    if sort == "top":
        url += "&t=month"
    return url


def _fetch_listing(subreddit: str, sort: str, query: str) -> list[dict[str, Any]]:
    """Fetch and parse one SVC listing page. Never raises."""
    try:
        text = client.get_text(
            _svc_url(subreddit, sort),
            timeout=SVC_TIMEOUT,
            accept="text/html",
        )
        return parse_cards(text, query) if text else []
    except Exception as e:
        logger.debug("SVC listing failed for r/%s/%s: %s", subreddit, sort, e)
        return []


def fetch_listings(
    subreddits: list[str],
    depth: Depth = "default",
    query: str = "",
) -> list[dict[str, Any]]:
    """Fetch scored listing cards from the SVC endpoint for multiple subreddits.

    Uses the shreddit ``/svc/shreddit/community-more-posts/`` endpoint (the same
    approach as mvanhorn/last30days-skill) which returns server-rendered
    ``<shreddit-post>`` elements with real upvote scores and comment counts.

    Unlike www.reddit.com's public HTML (JS shells ~8 KB), this endpoint
    returns rich server HTML (~876 KB) with all engagement data.
    """
    sorts = LISTING_SORTS.get(depth, LISTING_SORTS["default"])

    all_posts: list[dict[str, Any]] = []

    tasks = [(sub, sort) for sub in subreddits for sort in sorts]

    workers = min(MAX_WORKERS, len(tasks)) or 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_fetch_listing, sub, sort, query): (sub, sort) for sub, sort in tasks
        }
        for future in as_completed(futures):
            sub, sort = futures[future]
            try:
                all_posts.extend(future.result(timeout=SVC_TIMEOUT + 5))
            except Exception as e:
                logger.debug("SVC listing future failed for r/%s/%s: %s", sub, sort, e)

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
