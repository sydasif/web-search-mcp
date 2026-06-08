# Configuration

web-search-mcp uses environment variables for configuration, managed via `pydantic-settings`.

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GROQ_API_KEY` | API key for Groq services | Yes (for Groq tools) | None |

## Setup

You can set these variables in your shell or use a `.env` file:

```bash
export GROQ_API_KEY="your_api_key_here"
```

## Troubleshooting
If you encounter authentication errors when using `groq_browse`, `groq_research`, or `groq_analyze_page`, ensure that the `GROQ_API_KEY` is correctly exported in the environment where the MCP server is running.

---
[[Home]] | [[Architecture]] | [[Tools]] | [[Development]]
