# Unified `search_web` with provider selection (DDG + Exa)

**Date**: 2025-09-01
**Status**: Accepted — no code change
**Refs**: [`server.py:56-157`](../web_search_mcp/server.py), [`search/ddg.py`](../web_search_mcp/search/ddg.py), [`search/exa.py`](../web_search_mcp/search/exa.py)

## Problem

`search_web` currently unifies DuckDuckGo (DDG) and Exa search backends behind a single tool with a `provider` parameter:

- `provider="auto"` (default): try DDG first, fall back to Exa on error or zero results
- `provider="ddg"`: DDG only
- `provider="exa"`: Exa only

Should the backend be split into two separate tools (`search_duckduckgo` and `search_exa`) or kept unified?

## Decision

**Keep unified.** The single `search_web` tool with provider selection is the right design.

## Rationale

### 1. Auto-fallback is operationally valuable

The `"auto"` provider is the default and the most commonly used mode. It provides transparent resilience:

```
DDG succeeds → returned immediately
DDG errors or returns 0 results → Exa tried automatically
```

Splitting tools would require the LLM agent to decide *when* to call which backend, or to call both in sequence with retry logic — knowledge that should live in the tool, not in every caller.

### 2. One high-level capability is less tool clutter

MCP servers present their tool list to LLMs. Every tool adds:
- One entry in the tool schema (token budget)
- One decision point for the LLM routing logic
- One docstring the LLM must parse

A unified `search_web` with a documented `provider` parameter is **one tool with clear semantics**. Two tools doubles the surface without adding capability — they do the same thing (web search) with different backends.

### 3. Backward compatibility

Existing clients, workflows, and documentation reference `search_web(query=...)`. Splitting would require:
- Renaming the existing tool (breaking change)
- Adding two new tools
- Either keeping the old tool as deprecated or removing it
- Updating all agent configs that mount this server

### 4. No loss of explicit control

LLMs can still select the backend explicitly via `provider="ddg"` or `provider="exa"`. The unified tool does not hide the choice — it just makes the fallback automatic.

### 5. Caller graph is clean

Current call sites for the Exa search function:

| File | Line | Context |
|------|------|---------|
| `server.py` | 127 | `search_web` auto-fallback path |
| `search/ddg.py` | 53, 204 | `exa_fetch` used as page-fetch fallback in `fetch_page` |

`exa_search` is only called from `search_web`. Splitting would add minimal new code but remove the single point of fallback orchestration.

## What changes if we split (for completeness)

If splitting were chosen, the implementation would be:

```python
@mcp.tool(name="search_duckduckgo")
def search_duckduckgo(query: str, ...) -> ...:
    return ddg_search(SearchRequest(...))

@mcp.tool(name="search_exa")
def search_exa(query: str, ...) -> ...:
    return exa_search(...)
```

Tradeoffs lost:
- No automatic fallback from DDG → Exa
- LLM must understand both tools and decide when to retry with the other
- Doubling tool count in the MCP schema

## Verification

- E2E tests pass: `uv run pytest tests/test_e2e_tools.py` — **11 passed**
- `test_search_web` exercises the auto provider path
- `test_search_web_exa` exercises the explicit Exa provider path
- `test_search_web_provider_ddg` exercises the explicit DDG provider path

## Conclusion

The unified tool with provider selection preserves the fallback mechanism, minimizes tool surface, and maintains backward compatibility. The `provider` parameter gives explicit control when needed; `"auto"` is the pragmatic default.
