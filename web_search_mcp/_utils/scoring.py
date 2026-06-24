"""Relevance scoring utilities."""

from __future__ import annotations

import math
import re


def token_overlap_relevance(query: str, text: str) -> float:
    """Simple token overlap relevance score (0.0 to 1.0)."""
    if not query or not text:
        return 0.0
    q_tokens = set(re.findall(r"\w+", query.lower()))
    t_tokens = set(re.findall(r"\w+", text.lower()))
    if not q_tokens or not t_tokens:
        return 0.0
    intersection = q_tokens & t_tokens
    return round(len(intersection) / len(q_tokens), 3)


def compute_relevance(
    query: str,
    title: str,
    rank_index: int,
    engagement: int,
    engagement_weight: float = 20.0,
) -> float:
    """Blend text relevance with engagement signals.

    Args:
        query: Original search query
        title: Item title
        rank_index: Zero-based rank position
        engagement: Engagement signal (reactions, points, etc.)
        engagement_weight: Divisor for engagement boost (lower = more impact)

    Returns:
        Relevance score between 0.0 and 1.0

    """
    rank_score = max(0.3, 1.0 - (rank_index * 0.02))
    engagement_boost = min(0.2, math.log1p(engagement) / engagement_weight)

    if query:
        q_tokens = set(query.lower().split())
        t_tokens = set(title.lower().split())
        overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
        content_score = min(1.0, overlap * 2)
        return round(min(1.0, 0.6 * rank_score + 0.4 * content_score + engagement_boost), 2)
    return round(min(1.0, rank_score * 0.7 + engagement_boost + 0.1), 2)
