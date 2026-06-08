# Development Guide

## Environment Setup

This project uses `uv` for fast, reproducible dependency management.

```bash
# Install dependencies
uv sync

# Run the server
uv run web-search-mcp
```

## Testing

We use `pytest` for all tests.

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=web_search_mcp

# Run Groq-specific tests
uv run pytest tests/test_groq_search.py tests/test_groq_compound.py
```

## Coding Standards

### General
- **Python Version**: 3.11+
- **Linting**: `ruff`
- **Type Checking**: `mypy`

### Guidelines
- **Imports**: Use absolute imports.
- **Naming**: `snake_case` for functions, `PascalCase` for classes.
- **Type Hints**: Use Python 3.11+ union syntax (`str | None`).
- **Errors**: Use `utils.format_error()` for consistent MCP responses.

## Git Workflow
- Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
- Run `uv run ruff check . && uv run pytest` before committing.
- Use feature branches for new functionality.

---
[[Home]] | [[Architecture]] | [[Tools]] | [[Configuration]]
