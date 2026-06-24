"""Exa AI content fetch via HTTP MCP endpoint.

Uses the Exa MCP server (https://mcp.exa.ai/mcp) via JSON-RPC 2.0 over
HTTP POST with SSE responses. No mcporter or npm required — just httpx.
Optional EXA_API_KEY increases rate limits from free tier (20K req/month).

Used as a fallback by ddg.fetch_page when httpx + trafilatura fail.
"""

from __future__ import annotations

import json
import logging

import httpx

from .._config import settings
from .._utils import RateLimiter

logger = logging.getLogger(__name__)

EXA_MCP_URL = "https://mcp.exa.ai/mcp"
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
