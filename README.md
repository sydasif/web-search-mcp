# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

A comprehensive Model Context Protocol (MCP) server built with FastMCP that provides LLMs with real-time, high-fidelity access to the web. This server aggregates multiple search engines, social platforms, and developer tools into a single interface, allowing AI agents to perform deep research, track community sentiment, and analyze technical documentation.

## 🚀 Features

The server provides a diverse suite of tools categorized by their primary use case:

### 🌐 General Web Search & Retrieval

- **`search_web`**: Fast, free web search via DuckDuckGo. Ideal for broad discovery and news.
- **`fetch_web_page`**: High-fidelity text extraction from URLs with bot-detection bypass and multiple output formats.

### 💬 Social & Community Intelligence

- **`search_reddit`**: Keyless search for community discussions, opinions, and real-world user experiences.
- **`search_hackernews`**: Access to technical discourse, startup news, and developer opinions via the Algolia API.
- **`search_github`**: Search for Issues and PRs to track bugs, feature requests, and community sentiment.
- **`get_github_issue`**: Fetch full conversation threads from GitHub Issues/PRs, sorted by reactions.
- **`search_x`**: Real-time discourse and breaking news search via the Bird CLI (requires session cookies).

### 🎓 Academic & Reference

- **`search_arxiv`**: Specialized search for academic papers, supporting Lucene field prefixes (e.g., `au:`, `cat:`).
- **`search_wikipedia`**: Factual summaries and background research via the MediaWiki API.

### 🛠️ Developer Tooling

- **`compare_technologies`**: Side-by-side technical comparisons using real-world GitHub and registry data.

## 📋 Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)**: Recommended for installation and environment management.
- **External Tools** (Optional but recommended):
  - **`gh` CLI**: For authenticated GitHub search and issue retrieval.
  - **Node.js 22+**: Required for the vendored X/Twitter search CLI.

## ⚙️ Setup

### Installation

Install the server globally using `uv`:

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

### MCP Client Configuration

Add the server to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

## 🔐 Configuration & Authentication

Most tools are keyless. However, some require specific environment variables for full functionality:

| Tool            | Required/Optional | Environment Variable | Note                                                              |
| :-------------- | :---------------- | :------------------- | :---------------------------------------------------------------- |
| **GitHub**      | Optional          | `GITHUB_TOKEN` or `gh` CLI | Authenticates with the GitHub API for issues/PR search and full thread retrieval. |
| **X (Twitter)** | Required          | `AUTH_TOKEN`, `CT0`       | Session cookies extracted from a logged-in x.com browser session.               |
| **Exa AI**      | Optional          | `EXA_API_KEY`             | Increases rate limits for semantic search.                                      |

## 💡 Usage Examples

### Web Research

- **Broad Search**: `search_web(query="Latest NVIDIA H200 benchmarks")`
- **Targeted Docs**: `search_web(query="useEffect cleanup", domain="react.dev")`
- **Deep Read**: `fetch_web_page(url="https://docs.python.org/3/library/os.html")`

### Technical Analysis

- **Issue Tracking**: `search_github(query="uv package manager")`
- **Tech Comparison**: `compare_technologies(tech_a="FastAPI", tech_b="Django", category="framework")`

### Community Sentiment

- **Reddit**: `search_reddit(query="Best mechanical keyboards 2024", subreddits=["MechanicalKeyboards"])`
- **Hacker News**: `search_hackernews(query="MCP server architecture")`

## 🏗️ Project Structure

```text
web_search_mcp/
├── server.py          # Server entry point and tool registrations
├── search/            # Search engine implementations (DDG, Exa)
├── social/            # Social platform integrations (GH, HN, Reddit, X)
├── tools/             # Specialized tools (arXiv, Wiki, Registries)
├── _config/           # Settings and rate limiting
├── _http/             # Shared HTTP client logic
├── _models/           # Pydantic models for requests/responses
└── _utils/            # Formatting and scoring utilities
```

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/my-new-tool`.
3. Ensure all tests pass: `uv run pytest`.
4. Submit a pull request with a detailed description of the changes.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
