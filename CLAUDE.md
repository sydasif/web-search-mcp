# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**web-search-mcp** is a FastMCP server providing web search, content extraction, and research tools for LLM clients. Uses Python 3.11+ with uv for dependency management. The server implements the Model Context Protocol (MCP) to provide web search, content extraction, and AI-powered research capabilities to LLM clients.

**IMPORTANT**: Always use `uv` for dependency management and `uv run` for executing commands. Do not use pip or python directly.

## Architecture

The application follows a modular architecture with clear separation of concerns:

- **server.py**: FastMCP server entry point, defines 10 MCP tools exposed to clients
- **ddg.py**: DuckDuckGo search + web content extraction (`ddg_search`, `fetch_page`) using `trafilatura` — consolidated from the former `search.py` and `reader.py`
- **reddit/**: Keyless Reddit search via RSS + shreddit enrichment (`reddit_search_tool`)
- **hackernews.py**: Hacker News search via Algolia API (`search_hackernews`)
- **github.py**: GitHub Issues/PRs search (`search_github`)
- **polymarket.py**: Polymarket prediction market search via Gamma API (`search_polymarket`)
- **groq_tools.py**: Groq-powered tools — `browse` (GPT-OSS interactive search), `research` (auto-selecting compound search), `analyze_page` (URL visit + interpretation)
- **groq_client.py**: Shared Groq API client wrapper
- **http_client.py**: Shared HTTP client for keyless API calls
- **models.py**: Pydantic models for request/response validation (ErrorResponse, SearchRequest, PageResponse, SearchResult)
- **config.py**: Application settings via pydantic-settings (includes `groq_api_key`)
- **utils.py**: Shared utility functions for consistent error formatting, auth errors, and rate limiting

## MCP Tool Definitions

The server exposes ten tools across six engines:

### DuckDuckGo (free, fast, raw)

- `web_search`: Universal web and news search
- `fetch_page`: Extract clean text from URLs
- `search_docs`: Targeted search on specific domains (e.g., docs.python.org)

### Reddit (free, keyless, community signal)

- `reddit_search`: Search Reddit via keyless RSS + shreddit enrichment. Great for community sentiment, discussions, and real user experiences. Supports subreddit targeting, depth control, and time filters.

### Hacker News (free, tech discourse)

- `hackernews_search`: Search Hacker News via Algolia API. Great for developer opinions, startup discussions, and technical news. No API key needed.

### GitHub (free, code discussions)

- `github_search`: Search GitHub Issues and PRs. Great for bug reports, feature requests, and community sentiment on open-source projects. Optionally authenticates via `GITHUB_TOKEN` or `gh` CLI.

### Polymarket (free, prediction signals)

- `polymarket_search`: Search Polymarket prediction markets via Gamma API. Great for odds, market signals, and crowd-sourced probability estimates. No API key needed.

### Groq (requires API key)

- `groq_browse`: Interactive browser search via GPT-OSS models
- `groq_research`: Deep research — auto-selects search and tools to validate findings
- `groq_analyze_page`: Visit and analyze a URL — fetches and interprets in one step

## Development Commands

**IMPORTANT**: Always use `uv` for dependency management and `uv run` for executing commands. Do not use pip or python directly.

```bash
# Install dependencies (use uv, NOT pip)
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_ddg_functional.py

# Run a single test
uv run pytest tests/test_ddg_functional.py::TestDDGSearch::test_ddg_search_basic_text

# Run source-specific tests
uv run pytest tests/test_reddit.py tests/test_hackernews.py tests/test_github.py tests/test_polymarket.py

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
from .ddg import ddg_search
from .ddg import fetch_page as _fetch_page
from .groq_tools import browse as _groq_browse
from .groq_tools import research as _groq_research
from .groq_tools import analyze_page as _groq_analyze_page
from .reddit import reddit_search_tool as _reddit_search_tool
from .hackernews import search_hackernews as _search_hn
from .polymarket import search_polymarket as _search_pm
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
  - `web_search`, `search_docs` (discovery)
  - `fetch_page` (retrieval)
  - `groq_browse`, `groq_research`, `groq_analyze_page` (Groq tools)
- **Private functions**: Leading underscore `_helper_function`

### Error Handling

- Log errors with the module logger: `logger = logging.getLogger("web-search-mcp")`
- Use `utils.format_error()` for consistent error responses across all tools: `{"error": "message", "details": str(e)}`
- Use `utils.format_auth_error()` for missing API key errors
- Use `utils.format_empty_query_error()` for empty query errors
- Use `utils.format_empty_response_error(source)` for empty model responses
- Handle `None` values before slicing: `(info.get("key") or "")[:1000]`
- Include alternative tool suggestions in error messages

### MCP Tool Definition Pattern

```python
@mcp.tool(
    name="tool_name",
    annotations={
        "title": "Human-readable title",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
def tool_name(param: type, optional: type = default) -> str | dict:
    """
    One-line description with role and workflow guidance.

    Role: Description of when to use this tool.
    Workflow: How this fits with other tools.
    Alternative: Which tool to use instead for different needs.

    Args:
        param: Description
        optional: Description

    Returns:
        A dictionary for structured JSON response or a string for human-readable output

    Examples:
        Use when: ...
        Don't use when: ...

    Error Handling:
        - Error type: Suggested fix
    """
    return _internal_function(param)
```

### Testing

- Use `unittest.mock.patch` for external API calls
- Mock at the class level: `@patch("web_search_mcp.ddg.DDGS")` or `@patch("web_search_mcp.groq_client.Groq")`
- Test classes inherit from `unittest.TestCase` (optional, pytest can run functions too)
- Group related tests in classes with descriptive names: `TestDDGSearch`, `TestGroqBrowse`, `TestResearch`
- Use `assert` for assertions (S101 allowed in tests per ruff config)
- Coverage includes: success, error, empty input, and parameter forwarding

### Groq Tools Testing Pattern

```python
@patch("web_search_mcp.groq_client.Groq")
@patch("web_search_mcp.groq_client.settings")
def test_groq_search_success(self, mock_settings, mock_groq_cls):
    mock_settings.groq_api_key = "gsk_test123"
    mock_message = MagicMock()
    mock_message.content = "result"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_cls.return_value = mock_client

    result = browse("test query")
    assert isinstance(result, str)
```

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
