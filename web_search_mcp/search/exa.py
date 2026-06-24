"""Exa AI semantic search via HTTP MCP endpoint.

Uses the Exa MCP server (https://mcp.exa.ai/mcp) via JSON-RPC 2.0 over
HTTP POST with SSE responses. No mcporter or npm required — just httpx.
Optional EXA_API_KEY increases rate limits from free tier (20K req/month).

Three functions:
- exa_search(): basic semantic web search
- exa_search_advanced(): filtered search with domains, categories, dates, search type, content options
- exa_fetch(): fetch URL content as clean markdown
"""

from __future__ import annotations

import json
import logging

import httpx

from .._config import settings
from .._utils import RateLimiter

logger = logging.getLogger(__name__)

EXA_MCP_URL = "https://mcp.exa.ai/mcp"
EXA_ADVANCED_URL = "https://mcp.exa.ai/mcp?tools=web_search_advanced_exa"
EXA_TIMEOUT = 20

# Rate limit: 10 requests/minute (conservative for free tier 20K/month)
_exa_rate_limiter = RateLimiter(requests_per_minute=10)


def _post_jsonrpc(payload: dict, url: str = EXA_MCP_URL, timeout: int = EXA_TIMEOUT) -> dict | None:
    """Post a JSON-RPC request to Exa MCP. Returns parsed result or None."""
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    if settings.exa_api_key:
        headers["x-api-key"] = settings.exa_api_key
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Exa HTTP request failed: %s", e)
        return None

    # Parse SSE response (data: prefixed lines) or plain JSON
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except (json.JSONDecodeError, ValueError):
                continue
            if "result" in data:
                return data["result"]
            if "error" in data:
                logger.warning("Exa JSON-RPC error: %s", data["error"])
                return None
    try:
        return resp.json().get("result")
    except Exception:
        return None


def _extract_text(result: dict | None) -> str | None:
    """Extract text content from Exa MCP result. Returns None on error."""
    if not result:
        return None
    if not isinstance(result, dict):
        logger.warning("Exa returned non-dict result: %s", type(result).__name__)
        return None
    content = result.get("content", [])
    if not content or not isinstance(content[0], dict):
        return None
    text = content[0].get("text", "")
    if text.startswith("MCP error"):
        logger.warning("Exa error: %s", text[:200])
        return None
    return text


def exa_search(query: str, num_results: int = 5) -> list[dict] | None:
    """Basic semantic search via Exa.

    Returns list of {title, url, snippet} or None on failure.
    """
    if not query or not query.strip():
        return None
    num_results = max(1, min(num_results, 20))

    _exa_rate_limiter.acquire()

    result = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "web_search_exa",
                "arguments": {"query": query.strip(), "numResults": num_results},
            },
        }
    )
    text = _extract_text(result)
    if not text:
        return None

    results = []
    blocks = text.split("\n\n")
    for block in blocks:
        title = url = snippet = ""
        for line in block.split("\n"):
            if line.startswith("Title: "):
                title = line[7:]
            elif line.startswith("URL: "):
                url = line[5:]
            elif line.startswith("Highlights:"):
                snippet = line.split("\n", 1)[-1][:300] if "\n" in line else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
    if not results and text:
        logger.warning("Exa basic search returned text but no results parsed (len=%d)", len(text))
    return results if results else None


def exa_search_advanced(
    query: str,
    num_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search_type: str | None = None,
    contents: dict | None = None,
) -> dict | None:
    """Advanced search with filters. Returns structured JSON dict or None.

    Categories: company, research paper, news, tweet, personal site, linkedin, github.
    Search types: auto, instant, fast, deep-lite, deep, deep-reasoning.
    Contents: {"text": True, "highlights": True, "summary": True}
    """
    if not query or not query.strip():
        return None

    _exa_rate_limiter.acquire()
    num_results = max(1, min(num_results, 20))

    args: dict = {"query": query.strip(), "numResults": num_results}
    if include_domains:
        args["includeDomains"] = include_domains
    if exclude_domains:
        args["excludeDomains"] = exclude_domains
    if category:
        args["category"] = category
    if start_date:
        args["startPublishedDate"] = start_date
    if end_date:
        args["endPublishedDate"] = end_date
    if search_type:
        args["type"] = search_type
    if contents:
        args["contents"] = contents

    result = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "web_search_advanced_exa", "arguments": args},
        },
        url=EXA_ADVANCED_URL,
    )
    text = _extract_text(result)
    if not text:
        return None

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"results": [{"text": text, "title": "Untitled", "url": "#"}]}


def exa_fetch(urls: list[str], max_chars: int = 15000, timeout: int = EXA_TIMEOUT) -> str | None:
    """Fetch page content via Exa server-side render. Returns markdown or None.

    Handles JS-heavy pages, Cloudflare challenges, and paywalls that
    httpx cannot access.
    """
    if not urls:
        return None

    _exa_rate_limiter.acquire()

    result = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "web_fetch_exa",
                "arguments": {"urls": urls, "maxCharacters": max_chars},
            },
        },
        timeout=timeout,
    )
    return _extract_text(result)
