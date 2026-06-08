# Architecture

web-search-mcp follows a modular architecture with a clear separation of concerns to ensure maintainability and extensibility.

## Project Structure

- `server.py`: The entry point of the FastMCP server. It defines the MCP tools and exposes them to clients.
- `search.py`: Implements DuckDuckGo search logic, supporting both general text and news searches.
- `reader.py`: Handles web content extraction using `trafilatura`, providing clean text from various URL formats.
- `groq_search.py`: Integrates Groq GPT-OSS for interactive browser-based search.
- `groq_compound.py`: Implements advanced Groq Compound tools for deep research (`research`) and page interpretation (`analyze_page`).
- `models.py`: Contains Pydantic models for strict request/response validation.
- `config.py`: Manages application settings and API keys using `pydantic-settings`.
- `utils.py`: Provides shared utility functions for error formatting and rate limiting.

## Design Principles

1. **Modular Tooling**: Each search engine or extraction method is isolated in its own module.
2. **Strict Validation**: Pydantic models ensure that all inputs and outputs adhere to the expected schema.
3. **Consistent Error Handling**: A centralized utility (`utils.py`) ensures that all MCP tools return errors in a consistent format.
4. **Async-First**: Leverages Python's async capabilities for efficient network I/O.

---
[[Home]] | [[Tools]] | [[Development]] | [[Configuration]]
