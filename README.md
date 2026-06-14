# Web Search Plugin

A Claude Code plugin that provides web search, content extraction, and research tools. Search the web, Reddit, Hacker News, GitHub, X/Twitter, Wikipedia, arXiv, and package registries - all from your Claude session. Powered by DuckDuckGo with automatic Exa AI fallback for JS-heavy and Cloudflare-protected pages.

## Tools

### Web & Content Discovery

| Tool             | Description                                                               |
| :--------------- | :------------------------------------------------------------------------ |
| `search_web`     | Search the web via DuckDuckGo (text or news, domain-scoped)               |
| `search_exa`     | Semantic search via Exa AI (filters, search type, content options)        |
| `fetch_web_page` | Extract clean text content from any URL (Exa fallback for JS-heavy pages) |

### Community Platforms

| Tool                | Description                                              |
| :------------------ | :------------------------------------------------------- |
| `search_reddit`     | Search Reddit via keyless RSS + shreddit enrichment      |
| `search_hackernews` | Search Hacker News via Algolia API                       |
| `search_github`     | Search GitHub Issues and PRs                             |
| `search_x`          | Search X/Twitter (requires AUTH_TOKEN + CT0 cookies)     |
| `get_github_issue`  | Fetch a full GitHub Issue or PR thread with all comments |

### AI-Powered Research (requires GROQ_API_KEY)

| Tool           | Description                                         |
| :------------- | :-------------------------------------------------- |
| `groq_search`  | AI-powered web search via Groq (browse or compound) |
| `groq_analyze` | Visit and analyze a URL via Groq Compound           |

### Knowledge Bases

| Tool               | Description                                   |
| :----------------- | :-------------------------------------------- |
| `search_wikipedia` | Search Wikipedia and return full article text |
| `search_arxiv`     | Search arXiv for academic papers              |

### Developer Tooling

| Tool                   | Description                                                         |
| :--------------------- | :------------------------------------------------------------------ |
| `get_package_info`     | Look up a package from npm, PyPI, crates.io, or Go                  |
| `search_packages`      | Search packages by keyword across a registry                        |
| `analyze_error`        | Parse error messages and search Stack Overflow for solutions        |
| `compare_technologies` | Compare two technologies side-by-side with GitHub and registry data |

## Skills

This plugin bundles two skills:

- **research** (`/research`) — Deep research across multiple sources with breadth-first, depth-first methodology
- **debug** (`/debug`) — Debug errors, test failures, and runtime exceptions

## Configuration

| Variable       | Required | Description                                  |
| :------------- | :------- | :------------------------------------------- |
| `GROQ_API_KEY` | No       | For `groq_search` and `groq_analyze` tools   |
| `EXA_API_KEY`  | No       | For Exa AI search (free tier: 20K req/month) |
| `GITHUB_TOKEN` | No       | For higher GitHub API rate limits            |
| `AUTH_TOKEN`   | No       | For X/Twitter search                         |
| `CT0`          | No       | For X/Twitter search                         |

### Example `~/.profile` entries

Add these to your `~/.profile` (or equivalent shell profile) to make the vars available to Claude Code:

```bash
# Groq — for groq_search and groq_analyze
export GROQ_API_KEY="gsk_your_key_here"

# Exa — for search_exa (optional, increases rate limits)
export EXA_API_KEY="your_exa_key_here"

# GitHub — for higher API rate limits on issue/PR search
export GITHUB_TOKEN="ghp_your_token_here"

# X/Twitter — for search_x (AUTH_TOKEN and CT0 from browser cookies)
export AUTH_TOKEN="your_auth_token_here"
export CT0="your_ct0_here"
```

The `AUTH_TOKEN` and `CT0` cookies can be extracted from your browser after logging in to `x.com`. These are session cookies that expire periodically and need to be refreshed.

> **Note**: The `.mcp.json` configures the MCP server to read these same variables via `${VAR_NAME}` interpolation — no additional mapping needed once they're in your environment.

## Package Structure

```
web_search_mcp/
├── server.py              # MCP tool registration (thin layer)
├── _config/               # Settings (pydantic-settings) + business constants
│   ├── settings.py
│   └── limits.py
├── _models/               # Shared Pydantic models and type aliases
│   ├── responses.py
│   ├── requests.py
│   └── types.py
├── _utils/                # Formatting, scoring, rate limiting
│   ├── formatting.py
│   ├── scoring.py
│   └── rate_limiter.py
├── _http/                 # Shared httpx client
│   └── client.py
├── search/                # Web search engines
│   ├── ddg.py             # DuckDuckGo + Exa fallback
│   └── exa.py             # Exa AI semantic search
├── social/                # Social platforms
│   ├── github.py          # GitHub Issues/PRs
│   ├── hackernews.py      # Hacker News via Algolia
│   ├── x.py               # X/Twitter via Bird CLI
│   └── reddit/            # Reddit RSS + shreddit
│       ├── client.py
│       ├── engine.py
│       ├── models.py
│       └── parsers.py
└── tools/                 # Developer tools
    ├── arxiv.py           # arXiv academic papers
    ├── compare.py         # Technology comparison
    ├── errors.py          # Error parsing + Stack Overflow
    ├── groq_client.py     # Groq API client
    ├── groq_tools.py      # Groq search/analyze
    ├── registries.py      # npm/PyPI/crates.io/Go
    └── wikipedia.py       # Wikipedia articles
```

## Adding New Tools

1. Add your source module in the appropriate sub-package (`search/`, `social/`, or `tools/`)
2. Import and register the tool in `web_search_mcp/server.py`
3. Update this README

## Development

```bash
cd web-search
uv sync
uv run ruff check web_search_mcp/
uv run ruff format web_search_mcp/
uv run mypy web_search_mcp/
```

## License

MIT
