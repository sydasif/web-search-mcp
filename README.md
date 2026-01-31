# Web Search MCP Server

A FastMCP server providing unified web search (via DuckDuckGo) and weather data (via OpenMeteo) for LLM clients.

## Installation

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

## Tools

### 1. `search`
Unified tool for web, news, images, videos, and books.

**Parameters:**
- `query` (required): Search query
- `search_type`: `text` (default), `news`, `image`, `video`, `books`
- `max_results`: Default 5
- `time_range`: `d`, `w`, `m`, `y`
- `region`: e.g., `us-en`, `uk-en`
- `safesearch`: `moderate` (default), `off`, `on`
- `filters`: Dict for type-specific options:
  - **Images**: `size` (Small, Medium, Large, Wallpaper), `color`, `type_image`, `layout`, `license_image`
  - **Videos**: `resolution` (high, standart), `duration` (short, medium, long), `license_videos`

### 2. `get_current_weather` / `get_forecast`
**Parameters:**
- `latitude`, `longitude` (required)
- `days` (forecast only, 1-16, default 7)

## MCP Configuration

Add to your MCP settings (e.g., `claude_desktop_config.json` or `opencode.json`):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

## Development

```bash
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp
uv sync
uv run pytest
```
