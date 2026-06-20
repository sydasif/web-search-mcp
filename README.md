# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

A FastMCP server giving LLMs real-time access to the web — search, read articles, browse Reddit/HN, track GitHub issues, search arXiv, look up packages, and more. No API keys required for most tools.

---

## Quick Start

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

---

## Documentation

Full documentation:

| Page                                                                          | Contents                                              |
| ----------------------------------------------------------------------------- | ----------------------------------------------------- |
| [Home](https://github.com/sydasif/web-search-mcp/wiki)                        |                                                       |
| [Tools](https://github.com/sydasif/web-search-mcp/wiki/Tools)                 | All 14 tools, what they do, and when to use them      |
| [Tools Status](https://github.com/sydasif/web-search-mcp/wiki/Tools-Status)   | Live functional test results and known quirks         |
| [Configuration](https://github.com/sydasif/web-search-mcp/wiki/Configuration) | Environment variables, X/Twitter cookies, GitHub auth |
| [Architecture](https://github.com/sydasif/web-search-mcp/wiki/Architecture)   | Project structure, design principles, data flow       |
| [Development](https://github.com/sydasif/web-search-mcp/wiki/Development)     | Setup, testing, linting, coding standards             |
| [Plugins](https://github.com/sydasif/web-search-mcp/wiki/Plugin)              | Available plugins and their usage                     |

---

## License

[MIT](https://opensource.org/licenses/MIT)
