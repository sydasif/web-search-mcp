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

### `search_web_pages`

Search for web pages and general content.

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

Search for images and visual content.

**Returns**: Image data with dimensions and sources
- `title`: Image title/alt text
- `image`: Direct image URL
- `thumbnail`: Thumbnail URL
- `url`: Source page URL
- `height`/`width`: Image dimensions
- `source`: Image provider

### `search_videos`

Search for videos and multimedia content.

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
|-----------|------|---------|-------------|
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

This MCP server provides four specialized search tools for Claude Code.

#### Add to Claude Code:
```bash
# Add the MCP server to Claude Code
claude mcp add web-search -- /path/to/web-search/.venv/bin/python3 server.py

# Verify all tools are connected
claude mcp list
```

#### Available Tools:
Once configured, Claude Code will have access to all four search tools:
- `search_web_pages` - General web content
- `search_news` - Current news
- `search_images` - Visual content
- `search_videos` - Video content

**Claude Code will automatically choose the appropriate tool based on your query:**
- *"Find recent AI news"* → `search_news`
- *"Show me neural network diagrams"* → `search_images`
- *"Find Python tutorial videos"* → `search_videos`
- *"Explain machine learning"* → `search_web_pages`

### Manual Testing

Test individual tools directly:
```bash
# Test web articles
python3 -c "from main import search; print(search('artificial intelligence', 'text', 2))"

# Test news articles
python3 -c "from main import search; print(search('AI developments', 'news', 2))"

# Test images
python3 -c "from main import search; print(search('neural networks', 'image', 2))"

# Test videos
python3 -c "from main import search; print(search('Python tutorials', 'video', 2))"
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

### Web Page Search
```python
# Claude Code automatically chooses search_web_pages for:
"Explain quantum computing" → search_web_pages(query="quantum computing")
"What are the benefits of renewable energy?" → search_web_pages(query="renewable energy benefits")
```

### News Search
```python
# For current events and recent developments:
"What's the latest in AI development?" → search_news(query="AI development")
"Recent climate change news" → search_news(query="climate change")
```

### Image Search
```python
# For visual content and diagrams:
"Show me neural network diagrams" → search_images(query="neural network diagrams")
"Photos of solar panels" → search_images(query="solar panel photos")
```

### Video Search
```python
# For tutorials and demonstrations:
"Python programming tutorials" → search_videos(query="Python programming tutorials")
"AI explanation videos" → search_videos(query="AI explanation")
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