# Plan: Add Google Gemini as Fallback for Groq Tools

## Context

The three Groq-powered tools (`groq_browse`, `groq_research`, `groq_analyze_page`) currently fail when Groq is down or rate-limited. Adding Gemini as a fallback provider ensures the tools remain available. The fallback triggers on ALL Groq errors (not just transient), and uses `gemini-2.5-flash` as the model.

## Scope

4 files changed, ~40 lines net added. No behavioral change when Groq is healthy. No changes to existing test pass/fail status.

## Changes

### 1. `web_search_mcp/config.py` — add `gemini_api_key`

Add one field to `Settings`:
```python
gemini_api_key: str = ""
```
Env var: `SEARCH_MCP_GEMINI_API_KEY`. When empty, fallback is disabled (existing behavior preserved).

### 2. `pyproject.toml` — add `google-genai` dependency

```
uv add google-genai
```

Adds `google-genai` to the `dependencies` list in `pyproject.toml`.

### 3. `web_search_mcp/groq_client.py` — add fallback wrapper

**Add import:**
```python
from google import genai
from google.genai import types
```

**Add new function `_call_gemini`:**
- Accepts `messages` (list[dict]) and `max_tokens` (int)
- Extracts the last user message content as the prompt
- Creates `genai.Client(api_key=settings.gemini_api_key)`
- Calls `client.models.generate_content(model="gemini-2.5-flash", ...)`
- Returns a duck-typed response matching Groq's `.choices[0].message.content` shape
- Raises `GroqClientError` on failure (so existing error handling in groq_tools.py still works)

**Add new function `call_groq_api_with_fallback`:**
- Same signature as `call_groq_api`
- Calls `call_groq_api(...)` inside try
- On `GroqClientError` (any status code): if `settings.gemini_api_key` is set, call `_call_gemini` and return its response; otherwise re-raise
- Logs a warning when fallback activates

### 4. `web_search_mcp/groq_tools.py` — wire in the fallback

- Update import: add `call_groq_api_with_fallback`
- In `browse()` (line 44): replace `call_groq_api(` with `call_groq_api_with_fallback(`
- In `research()` (line 77): same replacement
- In `analyze_page()` (line 120): same replacement

### 5. `tests/test_groq_search.py` + `tests/test_groq_compound.py` — add fallback tests

New tests to add in `test_groq_search.py`:
- `test_groq_error_falls_back_to_gemini` — mock `call_groq_api` to raise `GroqClientError`, mock `genai.Client`, verify Gemini is called and result returned
- `test_no_gemini_key_raises` — mock Groq failure + empty gemini key, verify original error re-raised

New tests to add in `test_groq_compound.py`:
- `test_research_falls_back_to_gemini` — same pattern for `research()`
- `test_analyze_page_falls_back_to_gemini` — same pattern for `analyze_page()`

## Files touched

| File | Change |
|------|--------|
| `web_search_mcp/config.py` | Add `gemini_api_key: str = ""` |
| `pyproject.toml` | Add `google-genai` dependency |
| `web_search_mcp/groq_client.py` | Add `_call_gemini()`, `call_groq_api_with_fallback()` |
| `web_search_mcp/groq_tools.py` | Swap 3 calls to `call_groq_api_with_fallback` |
| `tests/test_groq_search.py` | Add 2 fallback tests |
| `tests/test_groq_compound.py` | Add 2 fallback tests |

## Verification

```bash
uv run ruff check .                 # lint passes
uv run ruff format --check .       # format passes
uv run pytest tests/test_groq_search.py tests/test_groq_compound.py -v  # all pass
uv run pytest                       # full suite passes
```

## Rollback

Revert `config.py` to remove `gemini_api_key`, revert `groq_tools.py` imports back to `call_groq_api`, remove the new functions from `groq_client.py`, and `uv remove google-genai`.
