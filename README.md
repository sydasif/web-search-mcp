# Web Search MCP Server

A FastMCP-based server that provides comprehensive web search functionality for LLM clients. Built with privacy-focused DuckDuckGo search engine.

## Installation

Install directly from GitHub:

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

Or clone and install:

```bash
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp
uv sync
uv develop
```

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv) package manager.

## Usage

The server provides four search tools:
- `search_web` - General web content
- `search_news` - News articles
- `search_images` - Images
- `search_videos` - Videos

### Parameters

All tools support:
- `query` (required): Search query string
- `max_results`: Number of results (default: 5)
- `time_range`: Filter by time ("d", "w", "m", "y" for day, week, month, year)
- `region`: Region code (e.g. "us-en", "uk-en", "de-de")
- `safesearch`: Safe search level ("moderate", "off", "on")
- `page`: Page number for pagination (default: 1)
- `backend`: Backend engine ("auto", "legacy", "api")

## MCP Integration

Configure in Claude Code (~/.claude.json):

```json
{
  "mcpServers": {
    "search-ninja": {
      "command": "web-search-mcp"
    }
  }
}
```

Configure in Opencode (~/.config/opencode/opencode.json):

```json
{
  "mcp": {
    "search-ninja": {
      "type": "local",
      "command": ["web-search-mcp"],
      "enabled": true
    }
  }
}
```

## Features

- Multiple content types (text, images, news, videos)
- Advanced filtering (time range, regions, safe search)
- Pagination support
- Backend selection options
- Privacy-focused (DuckDuckGo)
- Optimized for LLMs with structured JSON responses
- Direct integration without wrapper class for improved performance

## Testing

All tools have been thoroughly tested with various parameters:

- ✅ **search_web**: General web search with all DDGS-native parameters
- ✅ **search_news**: News search with time filtering and regional options
- ✅ **search_images**: Image search with comprehensive filtering
- ✅ **search_videos**: Video search with rich metadata

The server is fully functional and ready for production use.
