# Web Search MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-orange)](https://github.com/jlowin/fastmcp)

Web Search MCP gives your LLM real-time access to the web — from simple Google-style searches to deep AI-powered research. Search the web, read articles, check Reddit, browse Hacker News, look up Wikipedia, track GitHub issues, read full issue threads, follow X/Twitter discussions, explore prediction markets, and more.

No API keys required for most tools. Works out of the box.

---

## What This Does

When you ask your LLM "what's the latest on X?", it can only answer from its training data. That data is months or years old. Web Search MCP fixes this by connecting your LLM to live web sources through the [Model Context Protocol](https://modelcontextprotocol.io).

Here's what you get:

- **Search the web** — text and news search via DuckDuckGo
- **Read any article** — extract clean text from URLs, stripping ads and clutter
- **Search Reddit** — find real discussions and community sentiment
- **Search Hacker News** — developer opinions and tech discourse
- **Search Wikipedia** — factual summaries, background research, citations
- **Search GitHub** — find issues, PRs, and bug reports across repos
- **Read GitHub issues** — fetch full issue/PR threads with all comments, sorted by reactions
- **Search X/Twitter** — real-time posts and breaking news
- **AI-powered research** — let Groq's models search, browse, and synthesize for you

Most tools are **free and require no API keys**. A few need setup (detailed below).

---

## Quick Start (2 minutes)

### Step 1: Install

```bash
uv tool install git+https://github.com/sydasif/web-search-mcp.git
```

### Step 2: Add to Your MCP Client

Paste this into your MCP client config (Claude Desktop, VS Code, Cursor, etc.):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp"
    }
  }
}
```

That's it. You now have web search in your LLM.

### Step 3: Optional — Enable More Tools

Want Reddit, Hacker News, GitHub, or X/Twitter search? They work out of the box — no extra config needed.

Want AI-powered research via Groq? Add an API key:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "web-search-mcp",
      "env": {
        "SEARCH_MCP_GROQ_API_KEY": "gsk_your_key_here"
      }
    }
  }
}
```

[Get a free Groq API key here](https://console.groq.com/keys) — Groq's free tier is generous.

---

## What Can I Do With It?

Here are some real-world examples to get you started.

### Search the Web

```
Ask your LLM: "Search for the latest Python 3.13 features"

Behind the scenes:
  web_search("latest Python 3.13 features", search_type="text")
```

### Read an Article

```
Ask your LLM: "Read this article and summarize it: https://docs.python.org/3/whatsnew/3.13.html"

Behind the scenes:
  fetch_page(url="https://docs.python.org/3/whatsnew/3.13.html")
```

### Search Reddit for Real Opinions

```
Ask your LLM: "What do people on Reddit think about Rust vs Go for web backends?"

Behind the scenes:
  reddit_search(query="Rust vs Go web backend", subreddits=["rust", "golang"])
```

### Search Hacker News for Tech Discourse

```
Ask your LLM: "Find Hacker News discussions about LLM fine-tuning in 2024"

Behind the scenes:
  hackernews_search(query="LLM fine-tuning 2024")
```

### Search Wikipedia

```
Ask your LLM: "What is the history of the Python programming language?"

Behind the scenes:
  wikipedia_search(query="Python programming language")
```

This fetches the top matching article's full plain text (with section markers) plus a list of related articles. No API key needed.

### Search GitHub Issues

### Read a Full GitHub Issue Thread

```
Ask your LLM: "Read this issue and summarize the discussion: https://github.com/astral-sh/uv/issues/2000"

Behind the scenes:
  get_github_issue(url="https://github.com/astral-sh/uv/issues/2000")
```

This fetches the entire thread — title, body, state, reactions, and all comments sorted by popularity — as structured Markdown. Works with both issues and pull requests. Requires `gh` CLI installed and authenticated, or `GITHUB_TOKEN` environment variable.

### Search X/Twitter for Breaking News

```
Ask your LLM: "What's trending about AI on X right now?"

Behind the scenes:
  x_search(query="AI", depth="default")
```

### AI-Powered Deep Research

```
Ask your LLM: "Research the state of quantum computing in 2025 and validate the findings"

Behind the scenes:
  groq_search(query="state of quantum computing 2025")
```

### Look Up Package Info

```
Ask your LLM: "What's the latest version of FastAPI on PyPI?"

Behind the scenes:
  package_info(name="fastapi", registry="pypi")
```

### Search for Packages

```
Ask your LLM: "Find npm packages for async HTTP clients"

Behind the scenes:
  package_search(query="async http client", registry="npm")
```

### Debug an Error

```
Ask your LLM: "I'm getting 'TypeError: Cannot read property of undefined' in my React app"

Behind the scenes:
  translate_error(error_message="TypeError: Cannot read property 'map' of undefined")
```

This parses the error, detects JavaScript + React, searches Stack Overflow, and returns solutions.

### Compare Technologies

```
Ask your LLM: "Compare React vs Vue for a new project"

Behind the scenes:
  compare_tech(tech_a="React", tech_b="Vue", category="framework")
```

Returns GitHub stars, npm download counts, version info, license, and open issues side by side.

---

## Choosing the Right Tool

Not sure which tool to use? Here's a quick guide:

| What You Want                  | Use This Tool       | Why                                             |
| ------------------------------ | ------------------- | ----------------------------------------------- |
| Quick web search               | `web_search`        | Fast, free, no API key                          |
| Read a specific URL            | `fetch_page`        | Extracts clean text, strips ads                 |
| Search a specific site         | `web_search`        | Use `domain="docs.python.org"` to scope results |
| Reddit discussions             | `reddit_search`     | Real community opinions                         |
| Tech opinions                  | `hackernews_search` | Developer-focused discussions                   |
| Factual summaries              | `wikipedia_search`  | Encyclopedia articles with full text            |
| Bug reports / feature requests | `github_search`     | Issues and PRs across repos                     |
| Full issue/PR conversation     | `get_github_issue`  | Complete thread with all comments               |
| Real-time social media         | `x_search`          | Live posts and breaking news                    |
| AI-powered research            | `groq_search`       | AI searches, browses, and synthesizes           |
| Deep page analysis             | `groq_analyze_page` | AI reads AND interprets                         |
| Package info                   | `package_info`      | Version, downloads, license, deps               |
| Discover packages              | `package_search`    | Search npm, PyPI, crates.io, Go                 |
| Debug an error                 | `translate_error`   | Parse + search Stack Overflow                   |
| Compare technologies           | `compare_tech`      | GitHub stars, npm download stats                |

---

## How the Tools Connect

The best results come from combining tools. Here's the workflow that works best:

**Step 1: Discover** (free, fast)
Use DuckDuckGo tools to find relevant sources quickly.

```
web_search("Python async performance benchmarks 2025")
```

**Step 2: Read** (free, fast)
Pull the clean text from the most promising URLs.

```
fetch_page(url="https://example.com/benchmark-results")
```

**Step 3: Validate** (requires Groq API key)
Let AI cross-check and expand on what you found.

```
groq_search("Validate these Python async benchmark findings and find any contradictions")
```

This discovery → reading → validation pattern gives you the most reliable results.

---

## Environment Variables

| Variable                       | What It Does                                            | Default | Required?           |
| ------------------------------ | ------------------------------------------------------- | ------- | ------------------- |
| `SEARCH_MCP_GROQ_API_KEY`      | API key for Groq tools (search, analyze_page) | —       | Only for Groq tools |
| `SEARCH_MCP_RATE_LIMIT_SEARCH` | Max DDG search requests per minute                      | `30`    | No                  |
| `SEARCH_MCP_RATE_LIMIT_FETCH`  | Max page fetch requests per minute                      | `20`    | No                  |
| `AUTH_TOKEN`                   | X/Twitter session cookie                                | —       | Only for `x_search` |
| `CT0`                          | X/Twitter CSRF token cookie                             | —       | Only for `x_search` |
| `GITHUB_ISSUE_MAX_CHARS`       | Max characters for `get_github_issue` output            | `30000` | No                  |
| `WIKIPEDIA_MAX_CHARS`          | Max characters for `wikipedia_search` output            | `30000` | No                  |

### Getting X/Twitter Cookies

The `x_search` tool needs two cookies from a logged-in X session. Here's how to get them:

1. Log into [x.com](https://x.com) in your browser
2. Open DevTools (press F12)
3. Go to **Application** → **Cookies** → `https://x.com`
4. Find and copy the values for `auth_token` and `ct0`
5. Add them to your MCP config as `AUTH_TOKEN` and `CT0`

These cookies last about 24 hours. If X search stops working, refresh them.

---

## Fetch Backend Options

The `fetch_page` tool can use different HTTP backends. Some websites block automated requests, so having options helps.

| Backend          | How It Works                                         | When to Use                           |
| ---------------- | ---------------------------------------------------- | ------------------------------------- |
| `auto` (default) | Tries `httpx` first, falls back to `curl` if blocked | Best for most situations              |
| `httpx`          | Lightweight Python HTTP client                       | Fast, but some sites block it         |
| `curl`           | Pretends to be Chrome's browser (TLS impersonation)  | Bypasses Cloudflare and bot detection |

The `auto` backend handles this for you — it tries the fast option first and automatically switches if needed.

---

## Tool Reference

### DuckDuckGo Tools (free, no API key)

| Tool         | What It Does   | Key Parameters                                                                                                          |
| ------------ | -------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `web_search` | Search the web | `query`, `search_type` ("text" or "news"), `max_results`, `time_range` ("d", "w", "m", "y"), `region`, `page`, `domain` |
| `fetch_page` | Read a URL     | `url`, `output_format` ("txt", "markdown", "html", "json"), `include_metadata`, `max_length`, `backend`                 |

### Reddit Search (free, no API key)

| Tool            | What It Does  | Key Parameters                                                                   |
| --------------- | ------------- | -------------------------------------------------------------------------------- |
| `reddit_search` | Search Reddit | `query`, `subreddits` (list), `depth` ("quick", "default", "deep"), `time_range` |

### Hacker News Search (free, no API key)

| Tool                | What It Does       | Key Parameters                                               |
| ------------------- | ------------------ | ------------------------------------------------------------ |
| `hackernews_search` | Search Hacker News | `query`, `max_results`, `depth` ("quick", "default", "deep") |

### Wikipedia Search (free, no API key)

| Tool               | What It Does             | Key Parameters                             |
| ------------------ | ------------------------ | ------------------------------------------ |
| `wikipedia_search` | Search and read articles | `query`, `max_results` (default 5, max 20) |

### GitHub Search (free, needs `gh` CLI or `GITHUB_TOKEN`)

| Tool               | What It Does               | Key Parameters                                      |
| ------------------ | -------------------------- | --------------------------------------------------- |
| `github_search`    | Search Issues and PRs      | `query`, `max_results`, `depth`, `token` (optional) |
| `get_github_issue` | Fetch full issue/PR thread | `url` (full GitHub issue or PR URL)                 |

### X/Twitter Search (requires cookies)

| Tool       | What It Does     | Key Parameters                             |
| ---------- | ---------------- | ------------------------------------------ |
| `x_search` | Search X/Twitter | `query`, `from_date` (YYYY-MM-DD), `depth` |

### Groq Tools (requires API key)

| Tool                | What It Does                           | Best For                                          |
| ------------------- | -------------------------------------- | ------------------------------------------------- |
| `groq_search`       | AI-powered search (browse or compound) | Deep research, validation, multi-source synthesis |
| `groq_analyze_page` | Read AND interpret a URL               | Extracting specific insights from an article      |

### Developer Tools (free, no API key)

| Tool              | What It Does                                             | Key Parameters                                           |
| ----------------- | -------------------------------------------------------- | -------------------------------------------------------- |
| `package_info`    | Look up a specific package from npm, PyPI, crates.io, Go | `name`, `registry` ("npm", "pypi", "crates", "go")       |
| `package_search`  | Search packages by keyword across a registry             | `query`, `registry` (default "npm"), `max_results`       |
| `translate_error` | Parse errors and find Stack Overflow solutions           | `error_message`, `max_results`, `language` (auto-detect) |
| `compare_tech`    | Compare two technologies side-by-side                    | `tech_a`, `tech_b`, `category` ("framework", "library")  |

**Which Groq model should I use?**

- **`groq/compound-mini`** (default) — Faster, auto-research with 1 tool call. Start here.
- **`groq/compound`** — More thorough auto-research, up to 10 tool calls.
- **`openai/gpt-oss-20b`** — Interactive browsing with `reasoning_effort`. Good speed/quality balance.
- **`openai/gpt-oss-120b`** — Interactive browsing, best quality but slower.

---

## Troubleshooting

### "No results found" for web search

DuckDuckGo sometimes returns empty results for very specific or unusual queries. Try:

- Broadening your search terms
- Removing special characters
- Using a simpler query

### Cloudflare blocks when reading URLs

This happens when a website detects automated requests. The `fetch_page` tool handles this automatically:

- Default backend (`auto`) tries `httpx` first, then falls back to `curl` with Chrome impersonation
- If you're still blocked, try setting `backend="curl"` explicitly

### X/Twitter search not working

X cookies expire after ~24 hours. To fix:

1. Log into x.com again
2. Get fresh `auth_token` and `ct0` cookies (see [Getting X/Twitter Cookies](#getting-xtwitter-cookies) above)
3. Update your MCP config and restart the server

### Groq tools returning errors

- Check that `SEARCH_MCP_GROQ_API_KEY` is set correctly
- Make sure your Groq API key has credits (free tier available)
- If you see "Query too long", shorten your query to under 150 characters

### Rate limiting (429 errors)

DuckDuckGo will block you if you search too fast. The built-in rate limiter helps, but:

- Reduce `SEARCH_MCP_RATE_LIMIT_SEARCH` if you're hitting limits
- Add small delays between rapid searches
- Use `max_results` to get fewer results per query

### "get_github_issue" returns "gh CLI not installed"

The `get_github_issue` tool requires the [GitHub CLI (`gh`)](https://cli.github.com/) to fetch issue and PR threads:

```bash
# Install on Ubuntu/Debian
sudo apt install gh

# Install on macOS
brew install gh

# Authenticate (one time)
gh auth login
```

Alternatively, set `GITHUB_TOKEN` in your environment — `gh` will pick it up automatically without needing to run `gh auth login`. The `gh` binary itself is still required.

### Server won't start

Make sure you're using `uv` (not pip):

```bash
# Install
uv tool install git+https://github.com/sydasif/web-search-mcp.git

# Run directly
uv run web-search-mcp
```

---

## Frequently Asked Questions

**Do I need API keys?**

For most tools, no. Web search, Reddit, Hacker News, Wikipedia, and GitHub all work without any API key. You only need a Groq API key for the AI-powered tools (search, analyze_page) and X/Twitter cookies for X search. The `get_github_issue` tool needs the `gh` CLI installed (which uses your existing GitHub auth) or a `GITHUB_TOKEN` environment variable.

**Is this free?**

The DuckDuckGo, Reddit, Hacker News, Wikipedia, and GitHub tools are completely free. Groq has a generous free tier. X/Twitter uses your browser session.

**How is this different from just searching in the browser?**

Your LLM can't access the web on its own. This server gives it that ability through the Model Context Protocol. The LLM can search, read, analyze, and synthesize information in a single conversation turn.

**Can I use this with any LLM client?**

Yes, as long as it supports MCP — Claude Desktop, VS Code with Copilot, Cursor, Zed, and more.

**What about rate limits?**

The server includes built-in rate limiting to avoid getting blocked by DuckDuckGo. You can configure the limits via environment variables (defaults: 30 searches/min, 20 fetches/min).

---

## Development

<details>
<summary>Click to expand development instructions</summary>

### Setup

```bash
git clone https://github.com/sydasif/web-search-mcp.git
cd web-search-mcp
uv sync
```

### Run Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=web_search_mcp

# Single test file
uv run pytest tests/test_models.py

# Specific test
uv run pytest tests/test_models.py::test_search_request_valid_defaults
```

### Linting

```bash
uv run ruff check .
uv run ruff check --fix  # auto-fix issues
```

### Type Checking

```bash
uv run mypy web_search_mcp/
```

### Run the Server

```bash
uv run web-search-mcp
```

</details>

---

## License

[MIT License](https://opensource.org/licenses/MIT)

---

> **Acknowledgment:** This project is built on publicly available APIs, open-source libraries, and community research. DuckDuckGo, Reddit RSS, Hacker News Algolia API, Wikipedia MediaWiki API, GitHub REST API, and Groq's API are all used in accordance with their respective terms.
