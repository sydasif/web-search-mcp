# Web Search MCP Server

A FastMCP-based server that provides comprehensive web search functionality for LLM clients through the Model Context Protocol (MCP). Built with privacy-first DuckDuckGo search engine.

## Features

- 🔍 **Multiple Content Types**: Text, image, news, and video search capabilities
- 🎯 **Advanced Filtering**: Time-based filtering, regional results, content filtering
- 📊 **Smart Sorting**: Sort by relevance, date, or title
- 🚀 **Optimized for LLMs**: Structured JSON responses designed for AI consumption
- 🔒 **Privacy-Focused**: Uses DuckDuckGo (no tracking, no personalized ads)
- ⚡ **FastMCP Integration**: STDIO transport for seamless Claude Code integration

## MCP Tool

### `web_search_tool`

Perform web searches across multiple content types using DuckDuckGo.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | **required** | The search query string |
| `search_type` | string | `"text"` | Content type: `"text"`, `"image"`, `"news"`, `"video"` |
| `max_results` | integer | `5` | Number of results (1-20) |
| `time_range` | string | `null` | Time filter: `"day"`, `"week"`, `"month"`, `"year"` |
| `region` | string | `null` | Region code: `"us"`, `"uk"`, `"de"`, etc. |
| `sort_by` | string | `"relevance"` | Sort method: `"relevance"`, `"date"`, `"title"` |
| `filter_term` | string | `null` | Only show results containing this word/phrase |

#### Search Type Guide

- **`"text"`**: Web pages, articles, blogs, documentation, tutorials
- **`"news"`**: Recent news articles, current events, breaking stories
- **`"image"`**: Photos, diagrams, infographics, visual content
- **`"video"`**: Video tutorials, demonstrations, talks, media content

## Installation

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup
```bash
# Clone or navigate to the project directory
cd web-search

# Install dependencies
uv sync

# Activate virtual environment (optional)
source .venv/bin/activate
```

## Usage

### Claude Code Integration

This MCP server is designed specifically for Claude Code integration.

#### Add to Claude Code:
```bash
# Add the MCP server to Claude Code
claude mcp add web-search -- /path/to/web-search/.venv/bin/python3 server.py

# Verify it's connected
claude mcp list
```

#### Using the Web Search Tool:
Once configured, Claude Code can automatically use the web search tool. The server runs via STDIO transport and starts/stops on-demand.

**Example queries Claude Code can handle:**
- *"Find recent AI news"* → Uses news search
- *"Show me neural network diagrams"* → Uses image search
- *"Find Python tutorial videos"* → Uses video search
- *"Explain machine learning algorithms"* → Uses text search

### Manual Testing

Test the search functionality directly:
```bash
# Test text search
python3 -c "from main import search; print(search('artificial intelligence', 'text', 3))"

# Test news search
python3 -c "from main import search; print(search('AI developments', 'news', 3))"
```

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

## Examples

### Basic Text Search
```python
# Claude Code will automatically call this when you ask about topics
"Explain quantum computing" → searches for "quantum computing" with search_type: "text"
```

### News Search
```python
# When asking for current events
"What's the latest in AI development?" → uses search_type: "news"
```

### Image Search
```python
# When looking for visual content
"Show me diagrams of machine learning algorithms" → uses search_type: "image"
```

### Video Search
```python
# When asking for tutorials or demonstrations
"Find Python programming tutorials" → uses search_type: "video"
```

## Troubleshooting

### MCP Server Not Connected
```bash
# Check MCP server status
claude mcp list

# Re-add the server
claude mcp remove web-search
claude mcp add web-search -- /path/to/web-search/.venv/bin/python3 server.py
```

### Search Not Working
```bash
# Test search functions directly
cd /path/to/web-search
python3 -c "from main import search; result = search('test query', 'text', 1); print('OK' if result['results'] else 'Failed')"
```

### Virtual Environment Issues
```bash
# Ensure you're using the correct Python path
/path/to/web-search/.venv/bin/python3 --version
```

## Dependencies

- `ddgs>=9.10.0`: DuckDuckGo search API client
- `fastmcp>=0.3.0`: Model Context Protocol framework

## License

This project uses DuckDuckGo for search, which provides privacy-focused, tracker-free results.