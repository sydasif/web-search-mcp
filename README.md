# OmniSearch

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)
[![HOL Guard Scanner](https://img.shields.io/badge/HOL%20Guard-passing-00a67e)](https://github.com/hashgraph-online/hol-guard)

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

| Tool                | Description                                                                                                                                      | Best For                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `search_reddit`     | Keyless search for community discussions, opinions, and real-world user experiences via RSS + Shreddit enrichment + Arctic-Shift score backfill. | Product reviews, community sentiment, troubleshooting  |
| `search_hackernews` | Technical discourse, startup news, and developer opinions via the Algolia HN API.                                                                | Tech news, startup discussions, developer opinions     |
| `search_github`     | Search for Issues and PRs to track bugs, feature requests, and community sentiment. Requires `gh` CLI or `GITHUB_TOKEN`.                         | Bug tracking, feature requests, community sentiment    |
| `get_github_issue`  | Fetch full conversation threads from GitHub Issues/PRs, sorted by reactions with author/date/reactions metadata.                                 | Deep-diving into specific issues/PRs                   |
| `search_x`          | Real-time discourse and breaking news via Xquik API or vendored Bird CLI (requires session cookies or API key).                                  | Breaking news, community reactions, engagement signals |
| `search_linkedin`   | Search people, companies, jobs, posts via DuckDuckGo + Jina Reader (r.jina.ai). No API key needed.                                               | Professional profiles, company research, job search    |
| `search_digg`       | Curated AI discourse clusters from ~1000 high-signal X accounts via digg-pp-cli. TLDRs + top X posts per cluster.                                | AI trends, curated high-signal discourse               |
| `search_techmeme`   | Editorial tech news from live archive (2005+) via techmeme-pp-cli. Headlines with source attribution.                                            | Tech industry news, major announcements                |
| `search_polymarket` | Prediction markets with real-money odds via public Gamma API. Multi-query expansion + acronym credit.                                            | Forecasting, sentiment, real-money odds on events      |

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

| Tool                  | Required For                                                             | Installation                                                               |
| --------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| **`gh` CLI**          | Authenticated GitHub search & issue retrieval (higher rate limits)       | `brew install gh` / [github.com/cli/cli](https://github.com/cli/cli)       |
| **Node.js**           | Vendored Bird CLI for X/Twitter search (not needed with `XQUIK_API_KEY`) | 22+ recommended; `brew install node@22` / [nodejs.org](https://nodejs.org) |
| **`digg-pp-cli`**     | Digg AI 1000 curated clusters (free, no auth)                            | `npx -y @mvanhorn/printing-press-library install digg --cli-only`          |
| **`techmeme-pp-cli`** | Techmeme tech news archive search (free, no auth)                        | `npx -y @mvanhorn/printing-press-library install techmeme --cli-only`      |
| **`pdftotext`**       | Local corpus PDF extraction (optional, for future `--corpus` flag)       | `brew install poppler` / `apt install poppler-utils`                       |

---

## ⚙️ Installation

You have three options depending on your use case:

### Option A: Quick Run (via `uvx`)

Fastest way to try it out without cloning the repo. Add to your MCP client config:

```json
{
  "mcpServers": {
    "OmniSearch": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sydasif/web-search-mcp.git",
        "omnisearch"
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
    "OmniSearch": {
      "command": "omnisearch"
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
uv run omnisearch
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

| Variable                      | Required For                                                          | How to Get It                                               |
| :---------------------------- | :-------------------------------------------------------------------- | :---------------------------------------------------------- |
| `EXA_API_KEY`                 | Exa AI semantic search (optional fallback)                            | Sign up at [exa.ai](https://exa.ai)                         |
| `GITHUB_TOKEN`                | Higher GitHub API rate limits (optional)                              | Generate a [GitHub PAT](https://github.com/settings/tokens) |
| `AUTH_TOKEN`                  | X/Twitter search via Bird CLI (required)                              | Session cookie from x.com (see below)                       |
| `CT0`                         | X/Twitter search via Bird CLI (required)                              | Session cookie from x.com (see below)                       |
| `XQUIK_API_KEY`               | X/Twitter search via Xquik API (alternative to cookies)               | Sign up at [xquik.ai](https://xquik.ai)                     |
| `SEARCH_MCP_SEARXNG_URL`      | Optional SearXNG instance for keyless web search fallback             | Your SearXNG instance URL                                   |
| `SEARCH_MCP_CORPUS_DIRS`      | Local document directories for private search (colon-separated paths) | Paths to your `.md`/`.txt`/`.pdf` directories               |
| `SEARCH_MCP_DEFAULT_SOURCES`  | Fixed default source set (comma-separated, e.g. `reddit,x,github`)    | Source names from available sources                         |
| `SEARCH_MCP_INCLUDE_SOURCES`  | Opt-in additive sources (e.g. `perplexity,linkedin`)                  | Source names                                                |
| `SEARCH_MCP_EXCLUDE_SOURCES`  | Hard-exclude sources (e.g. `x,reddit`)                                | Source names                                                |
| `SEARCH_MCP_VERIFY_FRESHNESS` | Enable default fact-checking for Polymarket odds, GitHub stars, etc.  | `true` or `false`                                           |

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
# Broad search (auto: DDG first, falls back to Exa on error or zero results)
search_web(query="Latest NVIDIA H200 benchmarks")

# Force DDG explicitly
search_web(query="uv package manager", provider="ddg")

# Force Exa explicitly
search_web(query="uv package manager", provider="exa")

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

# LinkedIn professional search
search_linkedin(query="site reliability engineer", content_type="people")
search_linkedin(query="machine learning startup", content_type="companies")
search_linkedin(query="kubernetes devops", content_type="jobs")
search_linkedin(query="AI agents", content_type="posts")
```

### Academic Research

```python
# arXiv paper search with field prefixes
search_arxiv(query="au:Goodfellow AND cat:cs.LG")
search_arxiv(query="transformer attention", sort_by="submitted_date")

# Wikipedia background research
search_wikipedia(query="Quantum computing")
```

### AI Trends & Forecasting

```python
# Digg AI 1000 - curated clusters from high-signal X accounts
search_digg(query="AI agents")
search_digg(query="Claude Code", depth="deep")

# Techmeme - editorial tech news
search_techmeme(query="Apple WWDC")
search_techmeme(query="AI funding", depth="deep")

# Polymarket - prediction markets with real-money odds
search_polymarket(query="US election 2024")
search_polymarket(query="Fed rate cut")
search_polymarket(query="AI breakthrough", depth="deep")  # expanded query search
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
│   ├── linkedin/          # LinkedIn search via DDG + Jina Reader
│   │   ├── __init__.py    # LinkedIn search tool registration
│   │   └── client.py      # DDG search + Jina Reader enrichment
│   ├── reddit/            # RSS + Shreddit keyless pipeline
│   │   ├── client.py      # HTTP client with RSS parsing
│   │   ├── parsers.py     # RSS/HTML parsers
│   │   └── shreddit.py    # Shreddit comment enrichment
│   └── x.py               # X/Twitter search via Xquik API or vendored Bird CLI
├── tools/                 # Specialized reference utilities
│   ├── arxiv.py           # arXiv paper search (Lucene field prefixes)
│   ├── wikipedia.py       # Wikipedia MediaWiki API
│   ├── digg.py            # Digg AI 1000 clusters via digg-pp-cli
│   ├── techmeme.py        # Techmeme tech news via techmeme-pp-cli
│   └── polymarket.py      # Polymarket prediction markets via Gamma API
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

## 📐 Design Decisions

- [**search-backend-split**](docs/design-decisions/search-backend-split.md) — Why `search_web` unifies DuckDuckGo and Exa behind a single `provider` parameter instead of exposing two separate tools.

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
