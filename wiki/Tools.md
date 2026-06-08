# MCP Tools

The server exposes several tools across different engines, allowing LLMs to choose the right tool for the specific task.

## DuckDuckGo Engine (Free, Fast, Raw)
- `web_search`: Performs universal web and news searches. Use this for quick, broad discovery.
- `fetch_page`: Extracts clean, main-content text from a given URL. Ideal for reading articles.
- `search_docs`: Targeted search on specific domains (e.g., `docs.python.org`). Use this for technical documentation.

## Reddit Engine (Free, Community Signal)
- `reddit_search`: Search Reddit via keyless RSS and shreddit enrichment. Excellent for finding community sentiment, real-user experiences, and discussions.

## Groq GPT-OSS Engine (Requires API Key)
- `groq_browse`: Interactive browser search via GPT-OSS models. Provides a more synthesized view of the web.

## Groq Compound Engine (Requires API Key)
- `groq_research`: Deep research tool that auto-selects the best search strategy and tools to validate findings.
- `groq_analyze_page`: Visits a URL and interprets its content in a single step.

---
[[Home]] | [[Architecture]] | [[Development]] | [[Configuration]]
