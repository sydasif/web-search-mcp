"""Rerank tool: score and sort candidate texts against a query."""

from __future__ import annotations

import math

from web_search_mcp._utils.scoring import token_overlap_relevance

# Type ignore for flashrank - no stubs available
try:
    from flashrank import Ranker, RerankRequest  # type: ignore[import-untyped]
except ImportError:
    Ranker = None  # type: ignore[assignment,misc]
    RerankRequest = None  # type: ignore[assignment,misc]


def _length_penalty(text: str) -> float:
    """Apply length normalization penalty.

    Penalizes very short (<50 chars) and very long (>5000 chars) documents.
    Returns a multiplier between 0.5 and 1.0.
    """
    length = len(text)
    if length < 50:
        # Linear penalty for very short docs
        return max(0.5, length / 50)
    if length > 5000:
        # Logarithmic penalty for very long docs
        return max(0.5, 1.0 - (length - 5000) / 50000)
    return 1.0


def _ngrams(text: str, n: int = 3) -> set[str]:
    """Extract character n-grams from text."""
    text = text.lower()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _jaccard_similarity(a: str, b: str, n: int = 3) -> float:
    """Compute Jaccard similarity between two texts using character n-grams."""
    ngrams_a = _ngrams(a, n)
    ngrams_b = _ngrams(b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b
    return len(intersection) / len(union)


def _deduplicate_documents(
    scored: list[dict],
    threshold: float = 0.85,
    ngram_size: int = 3,
) -> list[dict]:
    """Remove near-duplicate documents, keeping highest-scored variant.

    Args:
        scored: List of scored documents with 'document' and 'score' keys
        threshold: Jaccard similarity threshold (0-1). Above = duplicate.
        ngram_size: Character n-gram size for similarity computation.

    Returns:
        Deduplicated list preserving original order of kept items.
    """
    if len(scored) <= 1:
        return scored

    kept: list[dict] = []
    for item in scored:
        doc = item["document"]
        is_duplicate = False
        for kept_item in kept:
            if _jaccard_similarity(doc, kept_item["document"], ngram_size) >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(item)
    return kept


def _enforce_chunk_diversity(
    scored: list[dict],
    max_per_parent: int = 1,
) -> list[dict]:
    """Enforce diversity by limiting chunks per parent document.

    Args:
        scored: List of scored documents. Items may have 'parent_id' in metadata.
        max_per_parent: Maximum chunks to keep per parent_id.

    Returns:
        Diversified list.
    """
    if max_per_parent <= 0:
        return scored

    parent_counts: dict[str, int] = {}
    diversified: list[dict] = []
    for item in scored:
        # Check for parent_id in metadata (if documents_meta was passed through)
        parent_id = item.get("parent_id")
        if parent_id is not None:
            count = parent_counts.get(parent_id, 0)
            if count >= max_per_parent:
                continue
            parent_counts[parent_id] = count + 1
        diversified.append(item)
    return diversified


# Cache for FlashRank instances
_FLASHRANK_RANKERS: dict[str, object] = {}


def _get_flashrank_ranker(model_name: str = "ms-marco-TinyBERT-L-2-v2"):
    """Get or create a cached FlashRank ranker instance."""
    if model_name not in _FLASHRANK_RANKERS:
        if Ranker is None:
            raise ImportError(
                "FlashRank not installed. Install with: uv pip install 'web_search_mcp[flashrank]'"
            )
        _FLASHRANK_RANKERS[model_name] = Ranker(model_name=model_name)
    return _FLASHRANK_RANKERS[model_name]


def _rerank_flashrank(
    query: str,
    documents: list[str],
    model_name: str = "ms-marco-TinyBERT-L-2-v2",
) -> list[dict]:
    """Rerank using FlashRank cross-encoder."""
    ranker = _get_flashrank_ranker(model_name)
    if RerankRequest is None:
        raise ImportError("FlashRank not available")

    passages = [{"text": doc, "id": idx} for idx, doc in enumerate(documents)]
    request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(request)

    scored = []
    for result in results:
        scored.append({
            "document": result["text"],
            "score": float(result["score"]),
            "index": result["id"],
        })
    return scored


def _compute_metadata_boost(
    meta: dict,
    weights: dict[str, float],
) -> float:
    """Compute metadata boost from document metadata.

    Args:
        meta: Document metadata dict
        weights: Feature weights (engagement, freshness, authority, etc.)

    Returns:
        Boost value (can be positive or negative)
    """
    boost = 0.0

    # Engagement boost (log scale, capped)
    if "engagement" in meta and "engagement" in weights:
        engagement = meta.get("engagement", 0)
        if engagement > 0:
            boost += weights["engagement"] * min(math.log1p(engagement) / 20.0, 0.3)

    # Freshness boost (newer = higher, decays over days)
    if "freshness_days" in meta and "freshness" in weights:
        days = meta.get("freshness_days", 365)
        if days >= 0:
            # Exponential decay: 1.0 at day 0, ~0.37 at 30 days, ~0.05 at 90 days
            boost += weights["freshness"] * max(0.0, math.exp(-days / 30.0) * 0.2)

    # Authority boost (source credibility)
    if "authority" in meta and "authority" in weights:
        authority = meta.get("authority", 0.0)
        if 0.0 <= authority <= 1.0:
            boost += weights["authority"] * authority * 0.15

    # Custom boost (generic)
    if "boost" in meta and "custom" in weights:
        boost += weights["custom"] * float(meta.get("boost", 0.0))

    return boost


def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int | None = None,
    backend: str = "token_overlap",
    model: str = "ms-marco-TinyBERT-L-2-v2",
    alpha: float = 0.3,
    documents_meta: list[dict] | None = None,
    weights: dict[str, float] | None = None,
    deduplicate: bool = True,
    dedup_threshold: float = 0.85,
    max_per_parent: int = 1,
) -> list[dict[str, object]]:
    """Rerank a list of documents against a query by relevance.

    Args:
        query: The search query to rank against
        documents: List of document strings to rank
        top_n: Optional limit on number of results to return
        backend: Scoring backend - "token_overlap" (default), "flashrank", or "hybrid"
        model: Model name for neural backends (FlashRank model)
        alpha: Weight for token_overlap in hybrid mode (0-1). Higher = more lexical.
        documents_meta: Optional list of metadata dicts parallel to documents.
            Supports keys: engagement (int), freshness_days (int), authority (0-1),
            boost (float), parent_id (str for chunk diversity)
        weights: Optional feature weights for blending and metadata.
            Keys: token (lexical), neural (semantic), engagement, freshness,
            authority, custom
            Defaults balance lexical + semantic + light metadata.
        deduplicate: Whether to remove near-duplicate documents (default True)
        dedup_threshold: Jaccard similarity threshold for deduplication (0-1)
        max_per_parent: Max chunks per parent_id to include in results (0 = unlimited)

    Returns:
        List of dicts with keys: "document" (str), "score" (float), "index" (int)
        where index is the original position in the input list.
        Sorted descending by score.
    """
    if not documents:
        return []

    if top_n is not None and top_n <= 0:
        return []

    # Default weights
    default_weights = {
        "token": 0.3,
        "neural": 0.6,
        "engagement": 0.05,
        "freshness": 0.03,
        "authority": 0.02,
        "custom": 0.0,
    }
    if weights:
        for k, v in weights.items():
            if k in default_weights:
                default_weights[k] = v
    weights = default_weights
    # Attach parent_id to scored items for chunk diversity enforcement
    def _attach_parent_ids(items: list[dict]) -> None:
        if documents_meta:
            for item in items:
                idx = item["index"]
                if isinstance(idx, int) and idx < len(documents_meta):
                    pid = documents_meta[idx].get("parent_id")
                    if pid is not None:
                        item["parent_id"] = pid

    # Normalize alpha from weights if not explicitly set
    alpha = weights.get("token", alpha)

    # Handle empty query - all scores 0.0 (but still apply metadata boosts)
    if not query or not query.strip():
        results = []
        for idx, doc in enumerate(documents):
            meta = documents_meta[idx] if documents_meta and idx < len(documents_meta) else {}
            meta_boost = _compute_metadata_boost(meta, weights)
            results.append({
                "document": doc,
                "score": round(max(0.0, meta_boost), 3),
                "index": idx,
            })
        if top_n is not None:
            return results[:top_n]
        return results

    # Route to backend
    if backend == "flashrank":
        try:
            scored = _rerank_flashrank(query, documents, model)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "FlashRank not available, falling back to token_overlap"
            )
            backend = "token_overlap"
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"FlashRank error: {e}, falling back to token_overlap"
            )
            backend = "token_overlap"
        else:
            # FlashRank succeeded - apply metadata boosts
            if documents_meta:
                for item in scored:
                    idx = item["index"]
                    meta = documents_meta[idx] if idx < len(documents_meta) else {}
                    boost = _compute_metadata_boost(meta, weights)
                    item["score"] = round(min(1.0, max(0.0, item["score"] + boost)), 3)
            scored.sort(key=lambda x: x["score"], reverse=True)  # type: ignore[return-value, arg-type]
            _attach_parent_ids(scored)
            # Apply deduplication and diversity
            if deduplicate:
                scored = _deduplicate_documents(scored, dedup_threshold)
            if max_per_parent > 0:
                scored = _enforce_chunk_diversity(scored, max_per_parent)

            if top_n is not None:
                return scored[:top_n]
            return scored

    if backend == "token_overlap":
        scored = []
        for idx, doc in enumerate(documents):
            if not doc or not isinstance(doc, str):
                scored.append(
                    {"document": str(doc) if doc is not None else "", "score": 0.0, "index": idx}
                )
                continue

            base_score = token_overlap_relevance(query, doc)
            penalty = _length_penalty(doc)
            final_score = round(base_score * penalty, 3)

            # Apply metadata boost
            if documents_meta:
                meta = documents_meta[idx] if idx < len(documents_meta) else {}
                boost = _compute_metadata_boost(meta, weights)
                final_score = round(min(1.0, max(0.0, final_score + boost)), 3)

            scored.append({"document": doc, "score": final_score, "index": idx})

    elif backend == "hybrid":
        # Get token overlap scores
        token_scored = []
        for idx, doc in enumerate(documents):
            if not doc or not isinstance(doc, str):
                token_scored.append(
                    {"document": str(doc) if doc is not None else "", "score": 0.0, "index": idx}
                )
                continue

            base_score = token_overlap_relevance(query, doc)
            penalty = _length_penalty(doc)
            final_score = round(base_score * penalty, 3)
            token_scored.append({"document": doc, "score": final_score, "index": idx})

        # Get neural scores
        try:
            neural_scored = _rerank_flashrank(query, documents, model)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "FlashRank not available, using token_overlap only for hybrid"
            )
            neural_scored = [
                {"document": d, "score": 0.0, "index": i}
                for i, d in enumerate(documents)
            ]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"FlashRank error: {e}, using token_overlap only for hybrid"
            )
            neural_scored = [
                {"document": d, "score": 0.0, "index": i}
                for i, d in enumerate(documents)
            ]

        # Blend scores
        neural_by_index: dict[int, float] = {
            item["index"]: float(item["score"]) for item in neural_scored
        }
        scored = []
        for item in token_scored:
            idx = int(item["index"])  # type: ignore[call-overload]
            token_score = float(item["score"])  # type: ignore[arg-type]
            neural_score = neural_by_index.get(idx, 0.0)

            # Base blend
            blended = (
                weights.get("token", alpha) * token_score
                + weights.get("neural", 1 - alpha) * neural_score
            )

            # Apply metadata boost
            if documents_meta:
                meta = documents_meta[idx] if idx < len(documents_meta) else {}
                boost = _compute_metadata_boost(meta, weights)
                blended = min(1.0, max(0.0, blended + boost))

            blended = round(blended, 3)
            scored.append({"document": item["document"], "score": blended, "index": idx})

    else:
        raise ValueError(
            f"Unknown backend: {backend}. "
            "Use 'token_overlap', 'flashrank', or 'hybrid'"
        )

    # Sort descending by score
    scored.sort(key=lambda x: x["score"], reverse=True)  # type: ignore[return-value, arg-type]
    _attach_parent_ids(scored)
    # Apply deduplication and diversity
    if deduplicate:
        scored = _deduplicate_documents(scored, dedup_threshold)
    if max_per_parent > 0:
        scored = _enforce_chunk_diversity(scored, max_per_parent)

    if top_n is not None:
        return scored[:top_n]
    return scored
