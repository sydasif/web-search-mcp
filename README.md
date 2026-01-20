# Web Search MCP Server

A FastMCP-based server that provides comprehensive web search functionality for LLM clients through the Model Context Protocol (MCP). Built with privacy-first DuckDuckGo search engine.

## Features

- 🔍 **Multiple Content Types**: Text, image, news, and video search capabilities
- 🎯 **Advanced Filtering**: Time-based filtering, regional results, content filtering
- 📊 **Smart Sorting**: Sort by relevance, date, or title
- 🚀 **Optimized for LLMs**: Structured JSON responses designed for AI consumption
- 🔒 **Privacy-Focused**: Uses DuckDuckGo (no tracking, no personalized ads)
- ⚡ **FastMCP Integration**: STDIO transport for seamless Claude Code integration

## MCP Tools

The server provides four specialized search tools, each designed for a specific type of content:

### `search_web`

Search for general web content.

**Returns**: Web pages, articles, blogs, and general web content

- `title`: Page title
- `href`: Page URL
- `body`: Page description

### `search_news`

Search for recent news and current events.

**Returns**: News items with publication metadata

- `date`: Publication date
- `title`: News headline
- `body`: Article summary
- `url`: Article URL
- `image`: Article image URL
- `source`: News source name

### `search_images`

Search for images including photos and visual content.

**Returns**: Image data with dimensions and sources

- `title`: Image title/alt text
- `image`: Direct image URL
- `thumbnail`: Thumbnail URL
- `url`: Source page URL
- `height`/`width`: Image dimensions
- `source`: Image provider

### `search_videos`

Search for videos including tutorials and multimedia content.

**Returns**: Video content with rich metadata

- `title`: Video title
- `description`: Video description
- `duration`: Video length
- `images`: Video thumbnails
- `published`: Upload date
- `statistics`: View counts
- `uploader`: Video creator

#### Common Parameters (All Tools)

| Parameter | Type | Default | Description |
| ----------- | ------ | --------- | ------------- |
| `query` | string | **required** | The search query string |
| `max_results` | integer | `5` | Number of results (1-20) |
| `time_range` | string | `null` | Time filter: `"day"`, `"week"`, `"month"`, `"year"` |
| `region` | string | `null` | Region code: `"us"`, `"uk"`, `"de"`, etc. |
| `sort_by` | string | `"relevance"` | Sort method: `"relevance"`, `"date"`, `"title"` |
| `filter_term` | string | `null` | Only show results containing this word/phrase |

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

#### Option 1: Clone and Install Locally

```bash
# Clone the repository
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp

# Install dependencies
uv sync

# Install as a command-line tool (so it can be run from any directory)
uv develop
```

#### Option 2: Install Directly from GitHub

You can also install directly from GitHub without cloning:

```bash
# Install directly from GitHub
uv tool install git+https://github.com/sydasif/web-search-mcp.git

# Or using the tarball
uv tool install https://github.com/sydasif/web-search-mcp/archive/main.tar.gz
```

If you don't have `uv` installed, install it first:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

#### Available Tools

Once configured, the search tools will be available to MCP-compatible clients:

- `search_web` - General web content
- `search_news` - Current news
- `search_images` - Visual content
- `search_videos` - Video content

## Integration

This server is compatible with multiple MCP-enabled platforms including Claude Code and Opencode.

> **Note**: The server must be running from the project directory for the MCP integration to work properly.

### Claude Code Integration

Integrate the web search server with Claude Code using the MCP (Model Context Protocol) configuration.

#### Global Configuration

To use the server globally across all projects, add it to Claude Code's global configuration (`~/.claude.json`):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

##### Example Configuration

After installing with `uv develop`, the server can be run from anywhere:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

#### Project-Specific Configuration

To enable the server for a specific project, navigate to your project directory and run:

```bash
claude mcp add
```

Then select the web-search server from the available options.

#### Using the Tools in Claude

Once configured, Claude will have access to four web search tools:

- `search_web` - General web content search
- `search_news` - News article search  
- `search_images` - Image search
- `search_videos` - Video search

Simply mention your search query in your conversation with Claude, and it will automatically use the appropriate search tool based on your request.

### Opencode Integration

The web search server can also be integrated with Opencode using MCP configuration.

#### Configuration

Add the web search server to your opencode configuration (`~/.config/opencode/opencode.json`):

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

##### Example Configuration

After installing with `uv develop`, the server can be run from anywhere:

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

#### Using the Tools in Opencode

Once configured, you can use the web search tools in opencode by requesting searches in your conversations. The system will automatically provide access to:

- `search_web` - General web content search
- `search_news` - News article search
- `search_images` - Image search
- `search_videos` - Video search

## Running the Server

### Install as a Command-Line Tool (Recommended)

Install the server globally to use from any directory:

```bash
# Install in development mode (from project directory)
cd /home/zulu/Documents/web-search
uv develop
```

This creates a `web-search-mcp` command that can be run from any directory:

```bash
# Run from anywhere
web-search-mcp
```

### Alternative: Run Directly

You can also run the server directly from the project directory:

```bash
# Navigate to the project directory
cd /home/zulu/Documents/web-search

# Run the server (it will listen on stdio)
uv run python server.py
```

The server implements the Model Context Protocol and should be used with compatible MCP clients like Claude Code.

## Response Format

The server returns structured JSON responses optimized for LLM consumption:

### Text Search Response

```json
{
  "query": "artificial intelligence",
  "search_type": "text",
  "total_results": 3,
  "results": [
    {
      "title": "Artificial Intelligence - Wikipedia",
      "href": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "body": "Artificial intelligence (AI) is the intelligence of machines or software..."
    }
  ]
}
```

### News Search Response

```json
{
  "query": "AI news",
  "search_type": "news",
  "total_results": 2,
  "results": [
    {
      "title": "Latest AI Breakthrough Announced",
      "body": "Scientists announce major breakthrough in AI research...",
      "url": "https://example.com/news/ai-breakthrough",
      "date": "2026-01-20T10:00:00+00:00",
      "source": "Tech News Daily"
    }
  ]
}
```

### Image Search Response

```json
{
  "query": "neural networks",
  "search_type": "image",
  "total_results": 2,
  "results": [
    {
      "title": "Neural Network Diagram",
      "image": "https://example.com/images/neural-net.jpg",
      "url": "https://example.com/article",
      "height": 800,
      "width": 1200
    }
  ]
}
```

## Dependencies

- `ddgs>=9.10.0`: DuckDuckGo search API client
- `fastmcp>=0.3.0`: Model Context Protocol framework

## License

This project uses DuckDuckGo for search, which provides privacy-focused, tracker-free results.
