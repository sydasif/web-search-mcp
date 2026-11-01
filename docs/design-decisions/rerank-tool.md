# Rerank Tool (`rerank_results`)

**Date**: 2026-11-01
**Status**: Accepted — implemented
**Refs**: [`tools/rerank.py`](../web_search_mcp/tools/rerank.py), [`server.py:902-946`](../web_search_mcp/server.py), [`tests/test_rerank.py`](../tests/test_rerank.py), [`_utils/scoring.py`](../web_search_mcp/_utils/scoring.py)

## Problem

Search tools (`search_web`, `search_hackernews`, etc.) return 15-50 results ranked by the engine's own criteria (popularity, recency, SEO). LLM clients often need to re-prioritize those results against a *specific sub-question* before feeding them into a narrow context window. Reordering alone is trivial; the value is in the scoring quality that is hard to replicate client-side.

## Decision

Add a dedicated `rerank_results` MCP tool with three scoring backends, optional metadata boosting, deduplication, and chunk diversity.

## Architecture

### Backends

| Backend         | Mechanism                                              | Deps      | Latency   |
| --------------- | ------------------------------------------------------ | --------- | --------- |
| `token_overlap` | `token_overlap_relevance()` x length penalty (default) | none      | ~0ms      |
| `flashrank`     | ONNX cross-encoder via FlashRank                       | flashrank | <50ms CPU |
| `hybrid`        | `alpha * lexical + (1-alpha) * neural`                 | flashrank | <50ms CPU |

- **Default is `token_overlap`** — zero new required dependencies, fully backward compatible.
- **Graceful fallback**: if `flashrank`/`hybrid` is requested but FlashRank is not installed, it logs a warning and falls back to `token_overlap`.
- **Ranker instances are cached** per model name (`_FLASHRANK_RANKERS` dict) to avoid reloading ONNX weights on every call.

### Optional Install

```bash
uv pip install 'web_search_mcp[flashrank]'   # ~23MB, ONNX CPU, no torch
```

### Scoring Pipeline

```
documents ──► score (backend) ──► + metadata boost ──► sort desc ──► dedup ──► chunk diversity ──► top_n
```

### Metadata Boosts (Phase 2)

`documents_meta` is a list of dicts parallel to `documents`. Supported keys:

| Key              | Type   | Effect                                             |
| ---------------- | ------ | -------------------------------------------------- |
| `engagement`     | int    | log-scaled boost, capped at +0.3                   |
| `freshness_days` | int    | exponential decay: exp(-days/30) * 0.2             |
| `authority`      | 0.0-1.0| linear boost * 0.15                                |
| `boost`          | float  | generic custom boost (weight: `custom`)            |
| `parent_id`      | str    | groups chunks for diversity enforcement            |

Weights are configurable via the `weights` param (keys: `token`, `neural`, `engagement`, `freshness`, `authority`, `custom`). Scores are clamped to [0.0, 1.0].

### Deduplication & Diversity (Phase 3)

| Feature           | Param             | Default | Mechanism                                  |
| ----------------- | ----------------- | ------- | ------------------------------------------ |
| Deduplication     | `deduplicate`     | `True`  | char 3-gram Jaccard >= `dedup_threshold` (0.85) = duplicate, keep highest-scored |
| Chunk diversity   | `max_per_parent`  | `1`     | max chunks per `parent_id` (`0` = unlimited) |

## API

```python
rerank_documents(
    query: str,
    documents: list[str],
    top_n: int | None = None,
    backend: str = "token_overlap",       # "token_overlap" | "flashrank" | "hybrid"
    model: str = "ms-marco-TinyBERT-L-2-v2",
    alpha: float = 0.3,
    documents_meta: list[dict] | None = None,
    weights: dict[str, float] | None = None,
    deduplicate: bool = True,
    dedup_threshold: float = 0.85,
    max_per_parent: int = 1,
) -> list[dict[str, object]]
# Returns: [{"document": str, "score": float, "index": int}, ...] sorted desc by score
```

## MCP Tool

Registered in `server.py` as `rerank_results` with `readOnlyHint: True`, `idempotentHint: True`, `openWorldHint: False`. Returns a JSON-serializable list of dicts (matches `search_hackernews`/`search_github` pattern). Exceptions are caught and returned via `format_error`.

## Why It Belongs in This Server

1. **Reuses existing scoring** — `token_overlap_relevance` from `_utils/scoring.py` is already used by HN/GitHub search; no duplicate implementation.
2. **Optional neural backend runs locally** — FlashRank ONNX (~23MB, CPU <50ms), no GPU/torch required.
3. **Zero new required deps** — default `token_overlap` path has no install cost.
4. **One tool, not two** — follows the `search_web` unified-tool precedent (see [search-backend-split.md](search-backend-split.md)): backend selection via parameter, not separate tools.

## Testing

- 26 unit tests in `tests/test_rerank.py` covering: exact/partial match, empty query/docs, `top_n` edge cases, index preservation, length penalty, dedup (exact + near-dup + threshold), chunk diversity, metadata boosts (engagement/freshness/authority), custom weights, malformed inputs.
- Full suite: **370 tests pass**, `ruff` clean, `mypy` clean.

## Security

- No network calls in the default path.
- FlashRank downloads ONNX model weights from HuggingFace on first use (cached locally).
- No secrets, no user input to shell commands.

## Future Work

- Expose `backend`/`documents_meta`/`weights` params through the MCP tool signature (currently only `query`, `documents`, `top_n` are exposed).
- Add `search_corpus` tool using `SEARCH_MCP_CORPUS_DIRS`.