# AGENTS.md - Web Search MCP Server

This file contains development standards and commands for agentic coding assistants working on the web-search-mcp project.

## Project Overview

A FastMCP-based server providing comprehensive web search functionality using DuckDuckGo's privacy-focused search engine. Supports text, news, images, videos, and books searches with advanced filtering options including:

- **Unified Search**: Single tool supporting text, news, images, videos, and books with type-specific filters
- **Text Search**: General web content with time and region filtering
- **News Search**: Recent news articles with publication dates
- **Image Search**: Visual content with size, color, type, layout, and license filters
- **Video Search**: Multimedia content with resolution, duration, and license filters
- **Books Search**: Publications and books from various sources

## Development Environment

- **Python**: 3.11+
- **Package Manager**: uv
- **Dependencies**: fastmcp, ddgs, pydantic, pydantic-settings, httpx
- **Framework**: Model Context Protocol (MCP)

## Build Commands

### Install Dependencies

```bash
uv sync
```

### Run Development Server

```bash
uv run web-search-mcp
```

### Build Distribution

```bash
uv build
```

## Testing Commands

### Run All Tests

```bash
uv run pytest
```

### Run Single Test File

```bash
uv run pytest tests/test_file.py
```

### Run Specific Test

```bash
uv run pytest tests/test_file.py::TestClass::test_method
```

### Run Tests with Coverage

```bash
uv run pytest --cov=web_search_mcp --cov-report=html
```

## Code Quality Commands

### Lint Code (Recommended: Add ruff to dev dependencies)

```bash
uv run ruff check .
```

### Auto-fix Linting Issues

```bash
uv run ruff check . --fix
```

### Format Code

```bash
uv run ruff format .
# Alternative: uv format (built-in uv formatter)
```

### Type Check (Recommended: Add mypy to dev dependencies)

```bash
uv run mypy web_search_mcp/
```

## Code Style Guidelines

### Import Organization

```python
# Standard library imports
import os
from typing import Optional

# Third-party imports
from fastmcp import FastMCP

# Local imports
from .search import ddg_search
```

### Type Hints

- Use modern union syntax: `str | None` instead of `Optional[str]`
- Specify return types for all public functions
- Use `dict` for simple dictionaries, `Dict[str, Any]` for complex ones

### Naming Conventions

- **Functions/Methods**: snake_case (`ddg_search`, `search_web`)
- **Variables**: snake_case (`max_results`, `search_type`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TIMEOUT`)
- **Classes**: PascalCase (not currently used in this project)

### Docstrings

Use Google-style docstrings with Args and Returns sections:

```python
def search(
    query: str,
    search_type: str = "text",
    max_results: int = 5,
    **kwargs
) -> dict:
    """
    Unified search tool for web content, news, images, videos, and books.

    Args:
        query: Search query string
        search_type: Type of search ('text', 'image', 'news', 'video', 'books')
        max_results: Max number of results to return (default 5)
        **kwargs: Additional filters (size, color, resolution, etc.)

    Returns:
        Dict with query, search_type, total_results, results, and error if applicable
    """
```

### Pydantic Models

Use Pydantic models for structured data:

```python
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    search_type: str = "text"
    max_results: int = 5
    filters: dict = {}

class SearchResult(BaseModel):
    title: str
    url: str
    description: str | None = None

class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: list[SearchResult]
```

### Error Handling

- Use try/except blocks for external API calls
- Use structured logging with Python logging module
- Return error information in response dictionaries

```python
import logging

logger = logging.getLogger("web-search-mcp")

try:
    return ddg_search(query, search_type, **kwargs)
except Exception as e:
    logger.error(f"Search failed: {e}")
    return {"error": "Search failed", "details": str(e)}
```

### Code Structure

- Keep functions focused on single responsibilities
- Use descriptive variable names
- Avoid magic numbers - use named constants
- Prefer explicit over implicit

### File Organization

```
web_search_mcp/
├── __init__.py              # Package initialization
├── config.py               # Centralized configuration with Pydantic
├── models.py               # Pydantic models for Search/Weather
├── search.py               # Core search logic using DDGS directly
├── weather.py              # Weather API client with synchronous HTTP
└── server.py               # MCP server implementation
```

## Dependency Management

### Adding Dependencies

```bash
uv add package-name
```

### Adding Development Dependencies

```bash
uv add --dev ruff mypy pytest pytest-cov
```

### Updating Dependencies

```bash
uv lock --upgrade
uv sync
```

## Testing Standards

### Test File Naming

- `test_*.py` for test files
- Place in `tests/` directory (create if needed)

### Test Structure

```python
import pytest
from web_search_mcp.models import SearchRequest
from web_search_mcp.search import ddg_search

def test_ddg_search_basic():
    """Test basic search functionality."""
    req = SearchRequest(query="test query", max_results=1)
    result = ddg_search(req)
    assert "query" in result
    assert "results" in result
    assert len(result["results"]) <= 1

def test_ddg_search_with_filters():
    """Test search with time range filter."""
    req = SearchRequest(query="test query", time_range="d", max_results=2)
    result = ddg_search(req)
    assert result["search_type"] == "text"
    assert len(result["results"]) <= 2
```

### Mocking External Dependencies

Use pytest-mock or unittest.mock to mock DDGS calls for reliable testing. The project includes comprehensive mocks for all DDGS API calls to enable fast, reliable CI/CD testing without external API dependencies.

### Advanced Search Testing

When testing advanced filters, ensure to verify:

- Image filters: size, color, type, layout, license
- Video filters: resolution, duration, license
- Common parameters: time_range, region, safesearch, page, backend

## Commit Standards

### Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Before Committing

1. Run tests: `uv run pytest`
2. Run linting: `uv run ruff check .`
3. Run formatting: `uv run ruff format .`
4. Run type checking: `uv run mypy web_search_mcp/`

## Security Guidelines

- Never commit API keys, passwords, or sensitive credentials
- Validate all user inputs to prevent injection attacks
- Use HTTPS URLs for external requests
- Keep dependencies updated to patch security vulnerabilities

## Documentation

- Update README.md for any user-facing changes
- Add docstrings to all new public functions
- Update this AGENTS.md when development practices change

## Performance Considerations

- The DDGS library handles rate limiting internally
- Use context managers for resource cleanup (e.g., `with DDGS() as ddgs:`)
- Use context managers for HTTP clients (e.g., `with httpx.Client() as client:`)
- Consider caching for frequently requested searches (future enhancement)
- Monitor memory usage with large result sets

## Deployment

### Local Development

```bash
uv sync
uv run web-search-mcp
```

### Production Deployment

```bash
uv build
pip install dist/web_search_mcp-*.whl
```

## Troubleshooting

### Common Issues

- **Import errors**: Ensure `uv sync` has been run
- **DDGS connection issues**: Check network connectivity and DDGS service status
- **MCP protocol errors**: Verify FastMCP version compatibility

### Debug Mode

```bash
uv run python -m web_search_mcp.server
```

## Future Enhancements

- Implement caching layer
- Add rate limiting configuration
- Add metrics and monitoring
