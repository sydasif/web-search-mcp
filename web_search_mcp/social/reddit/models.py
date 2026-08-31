"""Keyless Reddit listing card fetch — scores posts via shreddit SVC endpoint.

Uses the SVC partial endpoint (``/svc/shreddit/community-more-posts/``) which
serves fully server-rendered ``<shreddit-post>`` HTML elements with real score,
comment count, and subreddit data.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..._models.types import Depth
from ..._utils import iso_to_date, iso_to_epoch, token_overlap_relevance
from . import client
from ._utils import assign_ids, dedupe_by, extract_attr
from .parsers import LISTING_SORTS, extract_post_ref

logger = logging.getLogger(__name__)

MAX_WORKERS = 3
SVC_TIMEOUT = 15

# Match <shreddit-post> custom elements (same pattern as the original parser)
_SHREDDIT_POST = re.compile(r"<shreddit-post(?=[\s>])[^>]*>")


def _post_id(url: str) -> str:
    """Extract post ID from a Reddit URL, or empty string if absent."""
    ref = extract_post_ref(url)
    return ref[1] if ref else ""


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

    Uses the shreddit ``/svc/shreddit/community-more-posts/`` endpoint which
    returns server-rendered ``<shreddit-post>`` elements with real upvote scores
    and comment counts.
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

    unique = dedupe_by(all_posts, key="post_id")
    assign_ids(unique, "L")
    return unique
