# Free Sources Integration (Digg, Techmeme, Polymarket, Arctic-Shift)

**Date**: 2025-10-04
**Status**: Accepted — implemented
**Refs**: [`tools/digg.py`](../web_search_mcp/tools/digg.py), [`tools/techmeme.py`](../web_search_mcp/tools/techmeme.py), [`tools/polymarket.py`](../web_search_mcp/tools/polymarket.py), [`social/reddit/arctic_shift.py`](../web_search_mcp/social/reddit/arctic_shift.py)

## Problem

The project needed to add high-value free search sources inspired by the last30days-skill, specifically:

- **Digg AI 1000** — Curated AI discourse clusters from ~1000 high-signal X accounts
- **Techmeme** — Editorial tech news from live archive (2005+)
- **Polymarket** — Prediction markets with real-money odds via Gamma API
- **Arctic-Shift** — Reddit score backfill for RSS-only posts

All sources must be **free, no API keys required**, and follow the project's architecture patterns.

## Decision

**Add all four sources** as separate MCP tools with binary-on-PATH gating for CLI-based sources, and direct API calls for Polymarket.

## Architecture

### Source Classification

| Source       | Type                    | Auth | Gating Mechanism                   |
| ------------ | ----------------------- | ---- | ---------------------------------- |
| Digg         | CLI (`digg-pp-cli`)     | None | Binary-on-PATH                     |
| Techmeme     | CLI (`techmeme-pp-cli`) | None | Binary-on-PATH                     |
| Polymarket   | HTTP API (Gamma)        | None | Always available                   |
| Arctic-Shift | HTTP API                | None | Always available (internal helper) |

### CLI-Based Source Pattern (Digg, Techmeme)

Following the existing X module pattern (`x.py:is_available()`):

```python
def is_available() -> bool:
    return shutil.which(CLI_BIN) is not None

# Tool returns ErrorResponse with install instructions if unavailable
if not is_available():
    return ErrorResponse(
        error="Source unavailable",
        details=f"{CLI_BIN} not on PATH. Install with: npx -y @mvanhorn/printing-press-library install {name} --cli-only"
    )
```

**Rationale**:

- Zero configuration for users who have the CLI
- Clear error with one-line install command
- Follows existing precedent (X module)

### HTTP API Source Pattern (Polymarket, Arctic-Shift)

Direct `get_json_client()` calls with:

- Generous timeouts (15-30s per depth)
- No auth required
- Graceful degradation (return `[]` on failure)

### Depth Tiers

All sources respect the unified `Depth` type (`quick` | `default` | `deep`) via `limits.py`:

```python
# limits.py
DEPTH_LIMITS = {
    "digg": {"quick": 8, "default": 20, "deep": 40},
    "techmeme": {"quick": 8, "default": 16, "deep": 30},
    "polymarket": {"quick": 1, "default": 3, "deep": 4},
    # ...
}
```

### Enrichment Limits

Sources with secondary enrichment (Digg post fetching) use `ENRICH_LIMITS`:

```python
ENRICH_LIMITS = {
    "digg": {"quick": 0, "default": 3, "deep": 5},
    # ...
}
```

## Implementation Details

### Digg (`tools/digg.py`)

- **Search**: `digg-pp-cli search "query" --since 30d --agent --limit N`
- **Enrichment**: `digg-pp-cli posts <cluster_id> --agent --by rank --limit 5` for top clusters
- **Relevance**: Rank decay + content score + rank boost (curatorial rank 1-50)
- **Output**: Clusters with TLDR, rank, post count, top X posts

### Techmeme (`tools/techmeme.py`)

- **Search**: `techmeme-pp-cli search "query" --json`
- **Date windowing**: Drops records outside `from_date..to_date` on record's own ISO date
- **Header filtering**: Rejects bare publication-name rows ("TechCrunch", etc.)
- **Relevance**: Rank decay + token overlap

### Polymarket (`tools/polymarket.py`)

- **API**: `https://gamma-api.polymarket.com/public-search` (15K req/10s free)
- **Query expansion**: 6 queries from topic (core + individual words + full topic)
- **Acronym credit**: "artificial general intelligence" → matches "AGI" in title
- **Topic filtering**: Proportional word overlap with domain-word fallback for sweeps
- **Relevance**: 70% content + 30% engagement (volume/liquidity)

### Arctic-Shift (`social/reddit/arctic_shift.py`)

- **API**: `https://arctic-shift.photon-reddit.com/api/posts/ids` (batch 50 IDs, max 3 batches)
- **Pacing**: 0.4s between batches, in-run cache
- **Listing fallback**: `/api/posts/search?subreddit=r/name&limit=N&sort=desc` for shreddit supplement
- **Integration**: Called from `engine.py:_discover()` to backfill scores for RSS-only posts

## Configuration

### Environment Variables (via `settings.py`)

| Variable                      | Purpose                                            |
| ----------------------------- | -------------------------------------------------- |
| `SEARCH_MCP_SEARXNG_URL`      | Optional SearXNG instance for keyless web fallback |
| `SEARCH_MCP_CORPUS_DIRS`      | Local document directories (colon-separated)       |
| `SEARCH_MCP_DEFAULT_SOURCES`  | Fixed default source set (e.g. `reddit,x,github`)  |
| `SEARCH_MCP_INCLUDE_SOURCES`  | Opt-in additive sources                            |
| `SEARCH_MCP_EXCLUDE_SOURCES`  | Hard-exclude sources                               |
| `SEARCH_MCP_VERIFY_FRESHNESS` | Default fact-checking flag                         |

### Limits (`limits.py`)

| Source     | quick | default | deep |
| ---------- | ----- | ------- | ---- |
| digg       | 8     | 20      | 40   |
| techmeme   | 8     | 16      | 30   |
| polymarket | 1     | 3       | 4    |

| Source        | quick | default | deep |
| ------------- | ----- | ------- | ---- |
| digg (enrich) | 0     | 3       | 5    |

## Security

| Source                       | Risk              | Mitigation                                                  |
| ---------------------------- | ----------------- | ----------------------------------------------------------- |
| Digg/Techmeme CLI            | Command injection | List-based `subprocess.run`, `shutil.which` for binary path |
| Polymarket/Arctic-Shift HTTP | SSRF              | Uses shared `get_json_client` with `validate_url`           |
| All                          | No secrets        | No API keys required                                        |

## Testing

- Unit tests for each module (existing test suite covers patterns)
- E2E tests: `uv run pytest tests/test_e2e_tools.py::test_search_digg`, etc.
- All 250 tests pass

## Verification

- `mypy` clean
- `ruff` clean
- All E2E tools tests pass

## Future Work

- Add `search_corpus` tool using `SEARCH_MCP_CORPUS_DIRS`
- Add `verify_freshness` default-on via `SEARCH_MCP_VERIFY_FRESHNESS`
- Consider `arxiv-pp-cli` as alternative arXiv backend
