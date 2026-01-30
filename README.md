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

The server provides seven search tools:
- `search_web` - General web content
- `search_news` - News articles
- `search_images` - Images with advanced filtering
- `search_videos` - Videos with quality filters
- `search_books` - Books and publications
- `get_current_weather` - Current weather conditions
- `get_forecast` - Daily weather forecast

### Parameters

#### Common Parameters (search tools)
- `query` (required): Search query string
- `max_results`: Number of results (default 5)
- `time_range`: Filter by time ("d", "w", "m", "y" for day, week, month, year)
- `region`: Region code (e.g. "us-en", "uk-en", "de-de")
- `safesearch`: Safe search level ("moderate", "off", "on")
- `page`: Page number for pagination (default 1)
- `backend`: Backend engine ("auto", "legacy", "api")

#### Weather Parameters (`get_current_weather`, `get_forecast`)
- `latitude` (required): Latitude of the location
- `longitude` (required): Longitude of the location
- `days` (optional, `get_forecast` only): Number of forecast days (1-16, default 7)

#### Image-Specific Parameters (`search_images`)
- `size`: Image size ("Small", "Medium", "Large", "Wallpaper")
- `color`: Color filter (color name or "Monochrome")
- `type_image`: Image type ("photo", "clipart", "gif", "transparent", "line")
- `layout`: Layout filter ("Square", "Tall", "Wide")
- `license_image`: License filter (various Creative Commons types)

#### Video-Specific Parameters (`search_videos`)
- `resolution`: Video resolution ("high", "standart")
- `duration`: Video duration ("short", "medium", "long")
- `license_videos`: License filter ("creativeCommon", "youtube")

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

- Multiple content types (text, images, news, videos, books)
- Real-time weather data (current and forecast) via OpenMeteo
- Advanced filtering (time range, regions, safe search)
- Pagination support
- Backend selection options
- Privacy-focused (DuckDuckGo)
- Optimized for LLMs with structured JSON responses
- Direct integration without wrapper class for improved performance

## Project Structure

```
web_search_mcp/
├── __init__.py      # Package initialization
├── search.py        # Core search logic
└── server.py        # MCP server implementation
```

## Testing

All tools have been thoroughly tested with various parameters:

- ✅ **search_web**: General web search with all DDGS-native parameters
- ✅ **search_news**: News search with time filtering and regional options
- ✅ **search_images**: Image search with comprehensive filtering
- ✅ **search_videos**: Video search with rich metadata
- ✅ **search_books**: Book search from various sources
- ✅ **get_current_weather**: Current weather data with robust error handling
- ✅ **get_forecast**: Daily forecast with customizable duration

### Running Tests

To run the test suite:

```bash
# Install development dependencies
uv sync

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_search.py

# Run tests with coverage
uv run pytest --cov=web_search_mcp
```

The test suite includes comprehensive unit tests with mocked DDGS API calls for reliable CI/CD testing, as well as integration tests with live API calls for functionality verification.

The server is fully functional and ready for production use.
