# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

A comprehensive **Model Context Protocol (MCP)** server built with **FastMCP** that provides LLMs with real-time, high-fidelity access to the web. This server aggregates multiple search engines, social platforms, and developer tools into a single interface, allowing AI agents to perform deep research, track community sentiment, and analyze technical documentation.

> **Design docs → [wiki](https://github.com/sydasif/web-search-mcp/wiki)** — tool selection guide, decision matrix, recommended workflows, tools status & known quirks, plugin setup, and development standards.

---

## 🚀 Features

The server provides a diverse suite of tools categorized by their primary use case:

### 🌐 General Web Search & Retrieval

| Tool         | Description                                                                                                                                                                               | Best For                                                        |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `search_web` | Fast web search via **DuckDuckGo** or **Exa** (SDK). Supports domain-scoping, date filtering, news mode, and geographic region. Default auto-provider tries DDG first, falls back to Exa. | Quick lookups, high-volume searches, pagination, broad coverage |
| `fetch_page` | High-fidelity text extraction from URLs with bot-detection bypass, SSRF protection (blocks private/internal IPs), and multiple output formats.                                            | Deep reading of search results, standalone URL fetching         |

### 💬 Social & Community Intelligence

| Tool                | Description                                                                                                              | Best For                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `search_reddit`     | Keyless search for community discussions, opinions, and real-world user experiences via RSS + Shreddit enrichment.       | Product reviews, community sentiment, troubleshooting  |
| `search_hackernews` | Technical discourse, startup news, and developer opinions via the Algolia HN API.                                        | Tech news, startup discussions, developer opinions     |
| `search_github`     | Search for Issues and PRs to track bugs, feature requests, and community sentiment. Requires `gh` CLI or `GITHUB_TOKEN`. | Bug tracking, feature requests, community sentiment    |
| `get_github_issue`  | Fetch full conversation threads from GitHub Issues/PRs, sorted by reactions with author/date/reactions metadata.         | Deep-diving into specific issues/PRs                   |
| `search_x`          | Real-time discourse and breaking news via Xquik API or vendored Bird CLI (requires session cookies or API key).          | Breaking news, community reactions, engagement signals |

### 🎓 Academic & Reference

| Tool               | Description                                                                                       | Best For                                          |
| ------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `search_arxiv`     | Specialized search for academic papers with Lucene field prefixes (`au:`, `ti:`, `cat:`, `abs:`). | Research papers, citations, literature reviews    |
| `search_wikipedia` | Factual summaries and background research via the MediaWiki API.                                  | Factual summaries, background research, citations |

---

## 📋 Prerequisites

| Requirement                               | Version | Notes                                                   |
| ----------------------------------------- | ------- | ------------------------------------------------------- |
| **Python**                                | 3.11+   | Required                                                |
| **[uv](https://github.com/astral-sh/uv)** | Latest  | Recommended for installation and environment management |

### Optional External Tools

| Tool         | Required For                                                             | Installation                                                               |
| ------------ | ------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| **`gh` CLI** | Authenticated GitHub search & issue retrieval (higher rate limits)       | `brew install gh` / [github.com/cli/cli](https://github.com/cli/cli)       |
| **Node.js**  | Vendored Bird CLI for X/Twitter search (not needed with `XQUIK_API_KEY`) | 22+ recommended; `brew install node@22` / [nodejs.org](https://nodejs.org) |

---

## ⚙️ Installation

You have three options depending on your use case:

### Option A: Quick Run (via `uvx`)

Fastest way to try it out without cloning the repo. Add to your MCP client config:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sydasif/web-search-mcp.git",
        "web-search-mcp"
      ]
    }
  }
}
```

### Option B: Permanent Install

Fastest startup times with a globally installed tool:

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

Then configure your MCP client:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

### Option C: Development Install

If you want to modify the code or contribute:

```bash
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp
uv sync
uv run web-search-mcp
```

### Verify It's Working

Once the server is running, try a simple search:

```
search_web(query="current weather in Tokyo")
```

---

## 🔐 Configuration & Authentication

Most tools work **out of the box with zero configuration**. The following environment variables are only needed for premium or authenticated features.

### Environment Variables Reference

| Variable        | Required For                                            | How to Get It                                               |
| :-------------- | :------------------------------------------------------ | :---------------------------------------------------------- |
| `EXA_API_KEY`   | Exa AI semantic search (optional fallback)              | Sign up at [exa.ai](https://exa.ai)                         |
| `GITHUB_TOKEN`  | Higher GitHub API rate limits (optional)                | Generate a [GitHub PAT](https://github.com/settings/tokens) |
| `AUTH_TOKEN`    | X/Twitter search via Bird CLI (required)                | Session cookie from x.com (see below)                       |
| `CT0`           | X/Twitter search via Bird CLI (required)                | Session cookie from x.com (see below)                       |
| `XQUIK_API_KEY` | X/Twitter search via Xquik API (alternative to cookies) | Sign up at [xquik.ai](https://xquik.ai)                     |

### Setting Up GitHub Authentication

**Option 1 — Recommended: Use `gh` CLI**

```bash
gh auth login
```

The server detects your local session automatically.

**Option 2: Manual Token**

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### Setting Up X/Twitter Authentication

X/Twitter search requires **either** session cookies **or** an API key.

**Option 1 — Session Cookies (Bird CLI):**

1. Log into `x.com` in your browser.
2. Open DevTools (F12) → **Application** (or Storage) → **Cookies** → `x.com`.
3. Copy the values for `auth_token` and `ct0`.
4. Export them in the shell where the MCP server runs:
   ```bash
   export AUTH_TOKEN="your_auth_token"
   export CT0="your_ct0"
   ```
   > **Note**: These are session cookies. If searches return 401s, refresh them by logging out and back in.

**Option 2 — Xquik API Key (Recommended):**

1. Sign up at [xquik.ai](https://xquik.ai) to get an API key.
2. Export it:
   ```bash
   export XQUIK_API_KEY="your_xquik_key"
   ```
   This bypasses the Node.js Bird CLI dependency entirely.

### Setting Up Exa AI (Optional)

Exa provides semantic search and JS-heavy page fallback:

```bash
export EXA_API_KEY="your_exa_key"
```

---

## 💡 Usage Examples

### Web Research

```python
# Broad search
search_web(query="Latest NVIDIA H200 benchmarks")

# Targeted documentation search
search_web(query="useEffect cleanup", domain="react.dev")

# News with region filter
search_web(query="elections", search_type="news", region="us-en", provider="exa")

# Date-filtered search
search_web(query="uv package manager", time_range="w", provider="auto")

# Deep read a page
fetch_page(url="https://docs.python.org/3/library/os.html")
```

### Technical Analysis

```python
# Track GitHub issues/PRs
search_github(query="uv package manager")

# Get full GitHub issue thread
get_github_issue(url="https://github.com/astral-sh/uv/issues/1")
```

### Community Sentiment

```python
# Reddit discussions
search_reddit(query="Best mechanical keyboards 2024", subreddits=["MechanicalKeyboards"])

# Hacker News technical discourse
search_hackernews(query="MCP server architecture")
```

### Academic Research

```python
# arXiv paper search with field prefixes
search_arxiv(query="au:Goodfellow AND cat:cs.LG")
search_arxiv(query="transformer attention", sort_by="submitted_date")

# Wikipedia background research
search_wikipedia(query="Quantum computing")
```

---

## 🏗️ Project Structure

```
web_search_mcp/
├── server.py              # Entry point: FastMCP init, @mcp.tool registrations
├── search/                # Search engine implementations
│   ├── ddg.py             # DuckDuckGo search + trafilatura page fetch
│   └── exa.py             # Exa SDK search & content fetch (lazy-init client)
├── social/                # Community platform integrations
│   ├── github.py          # GitHub Search API + gh CLI issue rendering
│   ├── hackernews.py      # Algolia HN API + comment enrichment
│   ├── reddit/            # RSS + Shreddit keyless pipeline
│   │   ├── client.py      # HTTP client with RSS parsing
│   │   ├── parsers.py     # RSS/HTML parsers
│   │   └── shreddit.py    # Shreddit comment enrichment
│   └── x.py               # X/Twitter search via Xquik API or vendored Bird CLI
├── tools/                 # Specialized reference utilities
│   ├── arxiv.py           # arXiv paper search (Lucene field prefixes)
│   └── wikipedia.py       # Wikipedia MediaWiki API
├── _config/               # Settings, env vars, rate limits, depth tiers
│   ├── settings.py        # pydantic-settings (EXA_API_KEY, SEARCH_MCP_ prefix)
│   └── limits.py          # Per-platform quick/default/deep limits, timeouts
├── _http/                 # Shared HTTP + SSRF protection
│   └── client.py          # validate_url, http_client, get_json_client
├── _models/               # Pydantic request/response models
│   ├── requests.py        # SearchRequest
│   ├── responses.py       # ErrorResponse, SearchResponse, PageResponse
│   └── types.py           # Depth, ResponseFormat, SearchType, FetchOutputFormat
├── _utils/                # Shared helpers
│   ├── formatting.py      # Markdown formatters, date/epoch utils
│   ├── rate_limiter.py    # Token-bucket rate limiter
│   └── scoring.py         # Relevance scoring
└── vendor/                # Vendored third-party tools
    └── bird-search/       # Node.js CLI for X/Twitter search (fallback when XQUIK_API_KEY unset)
```

---

## 🛠️ Tool Implementation Flow

When adding a new tool:

1. **Implement logic** in the appropriate module (`search/`, `social/`, or `tools/`)
2. **Define models** in `_models/` (request/response types)
3. **Register in `server.py`** using `@mcp.tool` decorator with a clear docstring (serves as the tool's description for the LLM)

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_module.py

# Run a specific test
uv run pytest tests/test_module.py::test_function_name

# Run with coverage
uv run pytest --cov=web_search_mcp
```

---

## 🔧 Troubleshooting

| Problem                                | Likely Cause                          | Solution                                                                |
| :------------------------------------- | :------------------------------------ | :---------------------------------------------------------------------- |
| **Auth errors on a tool**              | Env var not set in the server's shell | Export the variable in the same shell where the MCP server process runs |
| **GitHub returns empty results**       | Not authenticated                     | Run `gh auth login` or set `GITHUB_TOKEN`                               |
| **`search_x` returns 401**             | Expired X session cookies             | Re-extract `auth_token` and `ct0` from x.com                            |
| **`fetch_page` blocked by Cloudflare** | Bot detection                         | Try `backend="curl"` parameter                                          |
| **`search_arxiv` returns 503**         | Upstream arXiv maintenance            | Wait a few minutes and retry                                            |
| **Tool says "Query cannot be empty"**  | Missing or blank query                | Provide a non-empty search query                                        |

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/my-new-tool`
3. Ensure all tests pass: `uv run pytest`
4. Submit a pull request with a detailed description of the changes.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
