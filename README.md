# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

11 MCP tools for web search, content extraction, and research. Give your LLM clients real-time access to the web — from raw search to social media to AI-powered synthesis.

## ✨ Features

- **🌐 Deep Web Search**: Text and news search via DuckDuckGo.
- **📄 Content Extraction**: Read clutter-free full text from any URL using `trafilatura`. Supports multiple output formats (text, markdown, JSON), metadata extraction, and content filtering.
- **🛡️ Bot Detection Bypass**: Automatic fallback to Chrome TLS impersonation when sites block requests (Cloudflare, etc.).
- **💻 Technical Docs**: Targeted search for developer documentation (Python, React, etc.).
- **🚩 Reddit Search**: Keyless search for community sentiment and real user experiences. Uses a multi-tier RSS + HTML pipeline with query expansion and parallel fan-out for high-signal results.
- **💬 Hacker News Search**: Search tech discourse via the Algolia API. Find developer opinions, startup discussions, and technical news.
- **🐙 GitHub Search**: Search Issues and PRs across repositories — bug reports, feature requests, community sentiment on open-source projects.
- **🐦 X/Twitter Search**: Search X/Twitter via vendored Bird CLI for real-time discourse, breaking news, and community engagement signals. Requires `AUTH_TOKEN` and `CT0` cookies from a logged-in X session.
- **📊 Polymarket Search**: Search prediction markets for odds, market signals, and crowd-sourced probability estimates via Gamma API.
- **🤖 Groq Browser Search**: Interactive multi-page web browsing via Groq's GPT-OSS models.
- **🔬 Groq Deep Research**: Auto-selecting AI research via Groq's Compound system — validates and expands on initial results.
- **🔍 Groq Page Analysis**: Visit and interpret web pages via Groq Compound.

## 🚀 Quick Start

### Installation

Install directly using `uv`:

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

### Configuration

Add the server to your MCP client configuration (e.g., `claude_desktop_config.json`). You can optionally configure rate limits via environment variables to avoid DuckDuckGo blocking.

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp",
      "env": {
        "SEARCH_MCP_RATE_LIMIT_SEARCH": "30",
        "SEARCH_MCP_RATE_LIMIT_FETCH": "20",
        "SEARCH_MCP_GROQ_API_KEY": "gsk_your_key_here",
        "AUTH_TOKEN": "your_x_auth_token",
        "CT0": "your_x_ct0_cookie"
      }
    }
  }
}
```

**Available Environment Variables:**

- `SEARCH_MCP_GROQ_API_KEY`: Groq API key for GPT-OSS and Compound tools ([get one here](https://console.groq.com/keys)).
- `SEARCH_MCP_RATE_LIMIT_SEARCH`: Max DDG search requests per minute (default: `30`).
- `SEARCH_MCP_RATE_LIMIT_FETCH`: Max page fetch requests per minute (default: `20`).
- `AUTH_TOKEN`: X/Twitter `auth_token` cookie for `x_search` tool.
- `CT0`: X/Twitter `ct0` cookie for `x_search` tool.

> **Getting X/Twitter cookies:** Log into [x.com](https://x.com), open DevTools (F12) → Storage → Cookies → x.com, filter and copy the `auth_token` and `ct0` values as environment variables. These are session cookies for 24 hours — refresh them when searches stop working.

### Fetch Backend Options

The `fetch_page` tool supports three backend modes to handle sites with bot detection:

| Backend          | Description                                                              | Use Case                                    |
| ---------------- | ------------------------------------------------------------------------ | ------------------------------------------- |
| `auto` (default) | Tries `httpx` first, falls back to `curl` on 403 or Cloudflare challenge | Recommended for most use cases              |
| `httpx`          | Lightweight async HTTP client                                            | Fast, but may be blocked by some sites      |
| `curl`           | Uses `curl_cffi` with Chrome 131 TLS impersonation                       | Bypasses Cloudflare and similar bot filters |

## 🛠️ Tool Reference

### DuckDuckGo Tools (free, fast, raw data)

| Tool          | Description                                   | Key Parameters                                                                                                                                                                                                                         |
| ------------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `web_search`  | Universal search (Web, News)                  | `query`, `search_type` ("text", "news"), `max_results`, `time_range`, `region`, `page`, `response_format` ("json", "markdown")                                                                                                         |
| `fetch_page`  | Extract clean article text from a URL         | `url`, `output_format` ("csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"), `include_metadata`, `include_tables`, `include_comments`, `include_images`, `max_length`, `timeout`, `backend` ("httpx", "curl", "auto") |
| `search_docs` | Search specific tech documentation or domains | `query`, `domain` (e.g., "docs.python.org", "github.com")                                                                                                                                                                              |

### Reddit Tools (free, keyless, community signal)

| Tool            | Description                                 | Key Parameters                                                                                                                                |
| --------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `reddit_search` | Search Reddit for discussions and sentiment | `query`, `subreddits` (list), `depth` ("quick", "default", "deep"), `time_range` ("d", "w", "m", "y"), `response_format` ("json", "markdown") |

### Hacker News Tools (free, tech discourse)

| Tool                | Description                             | Key Parameters                                                                                       |
| ------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `hackernews_search` | Search Hacker News for tech discussions | `query`, `max_results`, `depth` ("quick", "default", "deep"), `response_format` ("json", "markdown") |

### GitHub Tools (free, code discussions)

| Tool            | Description                               | Key Parameters                                                                                                           |
| --------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `github_search` | Search GitHub Issues and PRs across repos | `query`, `max_results`, `depth` ("quick", "default", "deep"), `token` (optional), `response_format` ("json", "markdown") |

### Polymarket Tools (free, prediction signals)

| Tool                | Description                          | Key Parameters                                                                                       |
| ------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `polymarket_search` | Search Polymarket prediction markets | `topic`, `max_results`, `depth` ("quick", "default", "deep"), `response_format` ("json", "markdown") |

### Polymarket Tools (free, prediction signals)

| Tool                | Description                          | Key Parameters                                                                                       |
| ------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `polymarket_search` | Search Polymarket prediction markets | `topic`, `max_results`, `depth` ("quick", "default", "deep"), `response_format` ("json", "markdown") |

### X/Twitter Tools (requires cookies)

| Tool       | Description                              | Key Parameters                                                                                                  |
| ---------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `x_search` | Search X/Twitter for real-time discourse | `query`, `from_date` (YYYY-MM-DD), `depth` ("quick", "default", "deep"), `response_format` ("json", "markdown") |

### Groq Tools (requires API key, synthesized results)

| Tool                | Description                                                   | Key Parameters                                                                                                     |
| ------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `groq_browse`       | Interactive browser search via GPT-OSS models                 | `query`, `model` ("openai/gpt-oss-20b", "openai/gpt-oss-120b"), `reasoning_effort` ("low", "medium", "high")       |
| `groq_research`     | Deep research via Compound — auto-selects search and tools    | `query`, `model` ("groq/compound", "groq/compound-mini")                                                           |
| `groq_analyze_page` | Visit and analyze a URL via Compound — fetches AND interprets | `url`, `query` (what to extract, e.g. "Summarize the key points"), `model` ("groq/compound", "groq/compound-mini") |

### Workflow Guide

Use DuckDuckGo tools for **discovery** (fast, free), then Groq tools for **validation** (synthesized, comprehensive):

```
web_search("latest Python 3.13 features")
  → feed results into →
groq_research("Validate and expand on these findings")

fetch_page("https://docs.python.org/3/whatsnew/3.13.html")
  → feed raw content into →
groq_analyze_page("https://docs.python.org/3/whatsnew/3.13.html",
                   "Extract all performance improvements")
```

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

## 📄 License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).
