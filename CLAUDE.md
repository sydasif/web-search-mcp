# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Design docs → [wiki](https://github.com/sydasif/web-search-mcp/wiki)** — tool selection guide, design decisions, recommended workflows, tools status, plugin setup, and development standards.

## Common Commands

### Development

- **Install dependencies**: `uv sync`
- **Run server**: `uv run omnisearch` (or `uv run python -m web_search_mcp.server`)
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy .`

### Version / Release

- **Bump version**: update `pyproject.toml`, `web_search_mcp/__init__.py`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` to same version
- **After version bump**: run `uv sync` to update lockfile and rebuild package
- **Plugin auto-updates** on reload when version changes

### Testing

- **Run all tests**: `uv run pytest`
- **Run single test file**: `uv run pytest tests/test_module.py`
- **Run specific test**: `uv run pytest tests/test_module.py::test_function_name`
- **Run with coverage**: `uv run pytest --cov=web_search_mcp`

## Architecture

### High-Level Design

The project is a **FastMCP** server that exposes a suite of web search and data retrieval tools to LLMs. It follows a "Registry-Implementation" pattern:

- **Registry (`server.py`)**: The central point where `FastMCP` is initialized and tools are decorated with `@mcp.tool`. It handles the mapping between MCP tool definitions and the underlying Python implementations.
- **Implementation Layers**:
  - `search/`: Implements core web search engines (e.g., DuckDuckGo, Exa).
  - `social/`: Integrates with community platforms (GitHub, Reddit, Hacker News, X, LinkedIn).
  - `tools/`: Contains specialized utilities (arXiv, Wikipedia, Digg, Techmeme, Polymarket).
- **Internal Infrastructure (`_` prefixed folders)**:
  - `_http/`: Centralized HTTP client logic to ensure consistent timeouts, headers, error handling, and SSRF protection (blocks private/internal IP addresses).
  - `_models/`: Shared Pydantic models for requests and responses to ensure type safety across the server.
  - `_config/`: Manages settings, environment variables, and global rate limits. See `limits.py` for hard-coded result depth constraints (e.g., `quick`, `default`, `deep`) used by social tools.
  - `_utils/`: Low-level helpers for markdown formatting, result scoring, and date-window utilities.

### Project Layout

```text
web_search_mcp/
├── server.py          # Entry point: FastMCP init, @mcp.tool registrations
├── search/            # Search engine implementations
│   ├── ddg.py         # DuckDuckGo search + trafilatura page fetch
│   └── exa.py         # Exa SDK search & content fetch (lazy-init client)
├── social/            # Community platform integrations
│   ├── github.py      # GitHub Search API + gh CLI issue rendering
│   ├── hackernews.py  # Algolia HN API + comment enrichment
│   ├── linkedin/      # LinkedIn search via DDG + Jina Reader
│   │   ├── __init__.py    # LinkedIn search tool registration
│   │   └── client.py      # DDG search + Jina Reader enrichment
│   ├── reddit/        # RSS + Shreddit keyless pipeline
│   │   ├── client.py      # HTTP client with RSS parsing
│   │   ├── parsers.py     # RSS/HTML parsers
│   │   ├── models.py      # Shreddit card parsing
│   │   ├── engine.py      # Search pipeline + arctic-shift backfill
│   │   ├── arctic_shift.py # Arctic-Shift score enrichment
│   │   └── _utils.py      # Shared HTML/regex helpers
│   └── x.py           # X/Twitter search via Xquik API or vendored Bird CLI
├── tools/             # Specialized reference utilities
│   ├── arxiv.py       # arXiv paper search
│   ├── wikipedia.py   # Wikipedia MediaWiki API
│   ├── digg.py        # Digg AI 1000 clusters via digg-pp-cli
│   ├── techmeme.py    # Techmeme tech news via techmeme-pp-cli
│   └── polymarket.py  # Polymarket prediction markets via Gamma API
├── _config/           # Settings, env vars, rate limits, depth tiers
│   ├── settings.py    # pydantic-settings (EXA_API_KEY, SEARCH_MCP_ prefix)
│   └── limits.py      # Per-platform quick/default/deep limits, timeouts
├── _http/             # Shared HTTP + SSRF protection
│   └── client.py      # validate_url, http_client, get_json_client
├── _models/           # Pydantic request/response models
│   ├── requests.py    # SearchRequest
│   ├── responses.py   # ErrorResponse, SearchResponse, PageResponse
│   └── types.py       # Depth, ResponseFormat, SearchType, FetchOutputFormat
├── _utils/            # Shared helpers
│   ├── dates.py       # Time-range and date-window utilities
│   ├── formatting.py  # Markdown formatters, date/epoch utils
│   ├── rate_limiter.py # Token-bucket rate limiter
│   └── scoring.py     # Relevance scoring
└── vendor/            # Vendored third-party tools
    └── bird-search/   # Node.js CLI for X/Twitter search
```

### Tool Implementation Flow

When adding a new tool:

1. Define the logic in the appropriate module (`search/`, `social/`, or `tools/`).
2. Define necessary request/response models in `_models/`.
3. Register the tool in `server.py` using the `@mcp.tool` decorator, ensuring a clear docstring is provided as it serves as the tool's description for the LLM.
