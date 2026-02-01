# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

A comprehensive, production-ready research server for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Provide your LLM clients with real-time access to the web, weather data, and more.

## ✨ Features

- **🌐 Deep Web Search**: Text and news search via DuckDuckGo.
- **📄 Content Extraction**: Read clutter-free full text from any URL using `trafilatura`.
- **💻 Technical Docs**: Targeted search for developer documentation (Python, React, etc.).
- **🌤️ Weather Data**: Current conditions and forecasts via OpenMeteo.

## 🚀 Quick Start

### Installation

Install directly using `uv`:

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

### Configuration

Add the server to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

## 🛠️ Tool Reference

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `search_web` | Universal search (Web, News) | `query`, `search_type` ("text", "news"), `max_results`, `time_range`, `region`, `filters` |
| `fetch_page` | Extract clean article text from a URL | `url` |
| `search_docs` | Search specific tech documentation | `query`, `tech_stack` ("python", "react", "fastapi", "mcp", "httpx") |
| `get_weather` | Current conditions or forecast (defaults to 7-day forecast) | `latitude`, `longitude`, `mode` ("current"/"forecast"), `days` |

## 💻 Development

<details>
<summary>Click to expand development instructions</summary>

1. **Clone the repository**
   ```bash
   git clone https://github.com/sydasif/web-search-mcp.git
   cd web-search-mcp
   ```

2. **Sync dependencies**
   ```bash
   uv sync
   ```

3. **Run tests**
   ```bash
   # Run all tests
   uv run pytest

   # Run with coverage
   uv run pytest --cov=web_search_mcp
   ```

4. **Linting & Formatting**
   ```bash
   uv run ruff check .
   ```

</details>
