# Project Knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## Quickstart
- **Setup:** `uv sync` (uses `uv`, never pip)
- **Dev:** `uv run web-search-mcp` (stdio MCP server)
- **Test:** `uv run pytest` (all), `uv run pytest tests/test_models.py` (single file)
- **Lint:** `uv run ruff check .` (auto-fix: `uv run ruff check --fix`)
- **Typecheck:** `uv run mypy web_search_mcp/`

## Architecture
- **Language/Runtime:** Python 3.11+ with `uv` for dependency management
- **Framework:** FastMCP 2.14+ (Model Context Protocol server)
- **Entry point:** `web_search_mcp/server.py` → `main()` (stdio transport)
- **Key directories:**
  - `web_search_mcp/` — all source code (flat, no deep nesting)
  - `web_search_mcp/reddit/` — Reddit search engine (RSS + shreddit enrichment)
  - `web_search_mcp/vendor/` — vendored dependencies (e.g., Bird CLI for X/Twitter)
  - `tests/` — 16 test files, one per module/feature
- **Data flow:** Client → MCP tool (server.py) → engine module (ddg.py, reddit/, etc.) → external API → Pydantic model → response
- **Key modules:**
  - `server.py` — 17 MCP tool definitions, imports with `_alias` pattern to avoid name collisions
  - `ddg.py` — DuckDuckGo search + fetch_page (trafilatura for content extraction)
  - `groq_tools.py` / `groq_client.py` — AI-powered browse/research/analyze_page via Groq API
  - `registries.py` — npm/PyPI/crates.io/Go package lookup and search
  - `errors.py` — Error message parsing with language detection + Stack Overflow search
  - `compare.py` — Side-by-side tech comparison (GitHub stars, downloads, etc.)
  - `models.py` — Pydantic models (ErrorResponse, SearchRequest, PageResponse, etc.)
  - `config.py` — pydantic-settings config (env vars like `SEARCH_MCP_GROQ_API_KEY`)
  - `utils.py` — Shared helpers: `format_error()`, `format_auth_error()`, `format_empty_query_error()`
  - `http_client.py` — Shared HTTP client for keyless API calls
  - `x.py` — X/Twitter search via vendored Bird CLI (needs `AUTH_TOKEN` + `CT0` cookies)

## Conventions
- **Formatting:** ruff, line-length 100, trailing commas in multi-line calls
- **Type hints:** Python 3.11+ union syntax (`str | None`, not `Optional[str]`), `typing.Literal` for enum-like params
- **Naming:** `snake_case` functions, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants, leading `_` for private functions
- **Imports:** absolute imports, sorted by ruff, `from .module import func as _func` alias pattern in server.py
- **Error handling:** Use `utils.format_error()` for consistent `{"error": "msg", "details": str(e)}` responses; use `format_auth_error()` for missing keys; use `format_empty_query_error()` for empty queries; use `format_empty_response_error(source)` for empty model responses
- **Testing:** `unittest.mock.patch` at class/module level (e.g., `@patch("web_search_mcp.ddg.DDGS")`), test classes in `TestFoo` naming, assertions via `assert`
- **MCP tool pattern:** `@mcp.tool(name=..., annotations={...})` with docstring containing Role/Workflow/Alternative/Args/Returns/Examples/Error Handling sections
- **Git:** Conventional commits (`feat:`, `fix:`, `docs:`), atomic commits, `git add <specific-file>` (not `git add .`)

## Gotchas
- **Never use pip or python directly** — always `uv run ...` for commands
- **X/Twitter cookies expire ~24h** — users need to refresh `AUTH_TOKEN` and `CT0`
- **Groq tools need API key** — set `SEARCH_MCP_GROQ_API_KEY` env var; free tier at console.groq.com
- **GitHub issue thread needs `gh` CLI** — install and auth with `gh auth login`, or set `GITHUB_TOKEN`
- **DuckDuckGo rate limits** — defaults 30 searches/min, 20 fetches/min; configurable via env vars
- **Cloudflare blocks** — `fetch_page` auto-retries with curl backend; set `backend="curl"` explicitly if still blocked
- **Server import collisions** — server.py uses `_alias` pattern for all engine imports to avoid shadowing tool function names
- **Test patterns vary** — some tests use `unittest.TestCase` classes, others use plain functions; follow the existing style in each test file
