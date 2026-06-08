# web-search-mcp

**web-search-mcp** is a FastMCP server providing web search, content extraction, and research tools for LLM clients. It implements the Model Context Protocol (MCP) to give LLMs access to real-time web information and deep research capabilities.

## Quick Start

### Prerequisites
- Python 3.11+
- `uv` for dependency management

### Installation
```bash
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp
uv sync
```

### Running the Server
```bash
uv run web-search-mcp
```

## Core Capabilities
- **Web Search**: Fast, raw search results via DuckDuckGo.
- **Content Extraction**: Clean text extraction from URLs.
- **Community Signal**: Reddit search for real-user experiences.
- **AI Research**: Deep research and page analysis via Groq GPT-OSS and Compound systems.

---
[[Architecture]] | [[Tools]] | [[Development]] | [[Configuration]]
