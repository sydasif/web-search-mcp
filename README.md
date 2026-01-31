# Web Search MCP Server

A FastMCP server providing comprehensive research capabilities for LLM clients:

- **Web Search** (DuckDuckGo) - text, news, images, videos, books
- **Web Content Extraction** (trafilatura) - read full articles
- **Wikipedia Search** - factual summaries
- **ArXiv Search** - scientific/technical papers
- **Documentation Search** - site-specific tech docs
- **Weather Data** (OpenMeteo) - current & forecast
- **Market Data** (Yahoo Finance) - stock prices

## Installation

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

## Tools

### 1. `search_web`

Unified tool for web, news, images, videos, and books.

**Parameters:**

- `query` (required): Search query
- `search_type`: `text` (default), `news`, `image`, `video`, `books` (supports plural forms too)
- `max_results`: Default 5
- `time_range`: `d`, `w`, `m`, `y`
- `region`: e.g., `us-en`, `uk-en`
- `safesearch`: `moderate` (default), `off`, `on`
- **Image Filters**: `size` (Small, Medium, Large, Wallpaper), `color`, `type_image`, `layout`, `license_image`
- **Video Filters**: `resolution` (high, standart), `duration` (short, medium, long), `license_videos`

### 2. `fetch_page`

Extracts clean text from a URL without ads/clutter.

**Parameters:**
- `url` (required): URL to extract content from

### 3. `search_wiki`

Searches Wikipedia for factual summaries.

**Parameters:**
- `query` (required): Search query

### 4. `search_arxiv`

Searches for scientific papers on ArXiv.

**Parameters:**
- `query` (required): Search query
- `max_results`: Default 3

### 5. `search_docs`

Searches technical documentation sites.

**Parameters:**
- `query` (required): What you're looking for
- `tech_stack`: `python` (default), `react`, `mcp`, `fastapi`, `httpx`

### 6. `get_weather` / `get_forecast`

**Parameters:**

- `latitude`, `longitude` (required)
- `days` (forecast only, 1-16, default 7)

### 7. `get_finance`

Gets stock price and company information.

**Parameters:**
- `symbol` (required): Stock ticker (e.g., `AAPL`, `TSLA`)

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
