# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development

- **Install dependencies**: `uv sync`
- **Run server**: `uv run web-search-mcp` (or `uv run python -m web_search_mcp.server`)
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy .`

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
  - `social/`: Integrates with community platforms (GitHub, Reddit, Hacker News, X).
  - `tools/`: Contains specialized utilities (arXiv, Wikipedia, Package registries).
- **Internal Infrastructure (`_` prefixed folders)**:
  - `_http/`: Centralized HTTP client logic to ensure consistent timeouts, headers, and error handling.
  - `_models/`: Shared Pydantic models for requests and responses to ensure type safety across the server.
  - `_config/`: Manages settings, environment variables, and global rate limits. See `limits.py` for hard-coded result depth constraints (e.g., `quick`, `default`, `deep`) used by social tools.
  - `_utils/`: Low-level helpers for markdown formatting and result scoring.

### Tool Implementation Flow

When adding a new tool:

1. Define the logic in the appropriate module (`search/`, `social/`, or `tools/`).
2. Define necessary request/response models in `_models/`.
3. Register the tool in `server.py` using the `@mcp.tool` decorator, ensuring a clear docstring is provided as it serves as the tool's description for the LLM.
