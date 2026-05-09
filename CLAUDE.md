# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**web-search-mcp** is a FastMCP server providing web search, content extraction, and research tools for LLM clients. Uses Python 3.11+ with uv for dependency management. The server implements the Model Context Protocol (MCP) to provide web search, content extraction, and weather data capabilities to LLM clients.

**IMPORTANT**: Always use `uv` for dependency management and `uv run` for executing commands. Do not use pip or python directly.

## Architecture

The application follows a modular architecture with clear separation of concerns:

- **server.py**: FastMCP server entry point, defines MCP tools exposed to clients
- **search.py**: DuckDuckGo search logic (`ddg_search` function) with text/news search capabilities
- **weather.py**: OpenMeteo API integration for current weather and forecast data
- **research.py**: Technical documentation search functionality for specific domains
- **reader.py**: Web content extraction using `trafilatura` with support for multiple formats
- **geocode.py**: OpenStreetMap (Nominatim) integration for geocoding addresses to coordinates
- **models.py**: Pydantic models for request/response validation
- **config.py**: Application settings via pydantic-settings

## MCP Tool Definitions

The server exposes five main tools:
- `search_web`: Universal web and news search
- `fetch_page`: Extract clean text from URLs
- `search_docs`: Targeted search on specific domains (e.g., docs.python.org)
- `get_weather`: Current weather or forecast data via OpenMeteo
- `get_location`: Convert location names/addresses to geographic coordinates using OpenStreetMap (Nominatim)

## Development Commands

**IMPORTANT**: Always use `uv` for dependency management and `uv run` for executing commands. Do not use pip or python directly.

```bash
# Install dependencies (use uv, NOT pip)
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_search.py

# Run a single test
uv run pytest tests/test_search.py::TestDDGSearch::test_ddg_search_basic_text

# Run with coverage
uv run pytest --cov=web_search_mcp

# Lint check
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix

# Type checking
uv run mypy web_search_mcp/

# Run server (stdio transport)
uv run web-search-mcp
```

## Code Style Guidelines

### Imports
- Use absolute imports: `from web_search_mcp.models import SearchRequest`
- Sort imports with ruff (configured in pyproject.toml)
- Group imports: stdlib → third-party → local
- Use `_alias` pattern for imports in server.py to avoid name collisions with tool functions:

```python
from .search import ddg_search
from .reader import fetch_page as _fetch_page
```

### Formatting
- Line length: 100 characters
- No enforced brace style for conditionals (use best judgment)
- Use trailing commas for multi-line calls

### Type Hints
- Use Python 3.11+ union syntax: `str | None` instead of `Optional[str]`
- Use `typing.Literal` for enum-like parameters
- Add return type annotations for all public functions
- Use `dict` for simple dict returns, Pydantic models for structured data

### Naming Conventions
- **Functions**: `snake_case` for all functions
- **Classes**: `PascalCase` for classes (e.g., `SearchRequest`)
- **Constants**: `SCREAMING_SNAKE_CASE`
- **MCP Tools**: Use `action_subject` pattern:
  - `search_web`, `search_docs` (discovery)
  - `fetch_page`, `get_weather`, `get_forecast` (retrieval)
- **Private functions**: Leading underscore `_helper_function`

### Error Handling
- Log errors with the module logger: `logger = logging.getLogger("web-search-mcp")`
- Return error dicts from tool functions: `{"error": "message", "details": str(e)}`
- Handle `None` values before slicing: `(info.get("key") or "")[:1000]`
- Avoid bare `except Exception`; catch specific exceptions when possible
- Always include context in error messages

### MCP Tool Definition Pattern
```python
@mcp.tool
def tool_name(param: type, optional: type = default) -> dict:
    """
    One-line description.

    Args:
        param: Description
        optional: Description

    Returns:
        Description of return dict
    """
    return _internal_function(param)
```

### Testing
- Use `unittest.mock.patch` for external API calls
- Mock at the class level: `@patch("web_search_mcp.search.DDGS")`
- Test classes inherit from `unittest.TestCase` (optional, pytest can run functions too)
- Group related tests in classes with descriptive names: `TestDDGSearch`
- Use `assert` for assertions (S101 allowed in tests per ruff config)

### Git Workflow
- Write descriptive commit messages following conventional commits: "feat: add X tool", "fix: handle Y error", "docs: update documentation"
- Run `uv run ruff check . && uv run pytest` before committing to ensure code quality and functionality
- Do not commit generated files (uv.lock is an exception)
- Use feature branches for new functionality: `git checkout -b feature/new-tool-name`
- Keep commits atomic and focused on a single change or related set of changes
- Only add files that are part of the specific changes: `git add <specific-file>` instead of `git add .`
- Sign off on commits that adhere to the Developer Certificate of Origin (DCO)

### Dependency and Execution Best Practices
- Always use `uv` for dependency management (not pip)
- Always use `uv run` to execute Python scripts and commands
- Never use `pip install` or `python script.py` directly
- For ad-hoc Python execution, use `uv run python -c "your code"`