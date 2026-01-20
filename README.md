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
- `max_results`: Number of results (1-20, default: 5)
- `time_range`: Filter by time ("day", "week", "month", "year")
- `region`: Region code ("us", "uk", "de", etc.)
- `sort_by`: Sort method ("relevance", "date", "title")
- `filter_term`: Only show results containing this word/phrase

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
- Advanced filtering (time range, regions)
- Privacy-focused (DuckDuckGo)
- Optimized for LLMs with structured JSON responses

## Testing

All tools have been thoroughly tested with various parameters:

- ✅ **search_web**: General web search with all parameters
- ✅ **search_news**: News search with date sorting and time filtering
- ✅ **search_images**: Image search with filtering capabilities
- ✅ **search_videos**: Video search with rich metadata

The server is fully functional and ready for production use.
