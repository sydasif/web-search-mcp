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

## MCP Integration

Configure in Claude Code (~/.claude.json):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

Configure in Opencode (~/.config/opencode/opencode.json):

```json
{
  "mcp": {
    "web-search": {
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
