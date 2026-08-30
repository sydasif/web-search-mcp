"""Test module for web-search-mcp.

Contains integration and internals tests for the web search MCP server."""
from __future__ import annotations

from typing import Any

import httpx

from web_search_mcp.social import x


def test_extract_xquik_items_accepts_known_envelopes() -> None:
    tweet = {"id": "1", "text": "hello"}

    assert x._extract_xquik_items({"tweets": [tweet]}) == [tweet]
    assert x._extract_xquik_items({"data": {"results": [tweet]}}) == [tweet]
    assert x._extract_xquik_items([tweet]) == [tweet]
    assert x._extract_xquik_items({"data": {"metadata": {"results": [tweet]}}}) == []


def test_parse_item_accepts_xquik_tweet_shape() -> None:
    item = x._parse_item(
        {
            "id": "123",
            "text": "Xquik search result",
            "createdAt": "2026-02-24T10:30:00.000Z",
            "likeCount": 7,
            "retweetCount": 3,
            "replyCount": 2,
            "author": {"username": "xquik"},
        },
        0,
        "xquik",
    )

    assert item == {
        "id": "X1",
        "text": "Xquik search result",
        "url": "https://x.com/xquik/status/123",
        "author_handle": "xquik",
        "date": "2026-02-24",
        "engagement": {"likes": 7, "retweets": 3, "replies": 2},
    }


def test_search_x_uses_xquik_when_api_key_is_set(monkeypatch: Any) -> None:
    calls: list[tuple[str, int, int]] = []

    def fake_run_xquik_search(query: str, count: int, timeout: int) -> dict[str, Any]:
        calls.append((query, count, timeout))
        return {
            "items": [
                {
                    "id": "123",
                    "text": "from Xquik",
                    "createdAt": "2026-02-24T10:30:00.000Z",
                    "author": {"username": "xquik"},
                },
            ],
        }

    def fail_if_called() -> bool:
        raise AssertionError("Bird CLI should not be checked when XQUIK_API_KEY is set")

    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    monkeypatch.setattr(x, "_run_xquik_search", fake_run_xquik_search)
    monkeypatch.setattr(x, "is_available", fail_if_called)
    monkeypatch.setattr(x, "is_authenticated", fail_if_called)

    result = x.search_x("mcp", from_date="2026-01-01", depth="quick")

    assert calls == [("mcp since:2026-01-01", 12, 30)]
    assert result[0]["text"] == "from Xquik"


def test_run_xquik_search_without_key_returns_empty(monkeypatch: Any) -> None:
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)

    assert x._run_xquik_search("mcp", 10, 30) == {"items": []}


def test_run_xquik_search_handles_http_status(monkeypatch: Any) -> None:
    class FailingResponse:
        status_code = 503

        def raise_for_status(self) -> None:
            request = httpx.Request("GET", x._XQUIK_SEARCH_URL)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("unavailable", request=request, response=response)

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, *_args: object, **_kwargs: object) -> FailingResponse:
            return FailingResponse()

    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    monkeypatch.setattr(x, "get_json_client", lambda timeout: Client())

    result = x._run_xquik_search("mcp", 10, 30)

    assert result == {"error": "Xquik X search returned HTTP 503", "items": []}


def test_run_xquik_search_handles_request_error(monkeypatch: Any) -> None:
    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, *_args: object, **_kwargs: object) -> object:
            raise httpx.ConnectError("network unavailable")

    monkeypatch.setenv("XQUIK_API_KEY", "test-api-key")
    monkeypatch.setattr(x, "get_json_client", lambda timeout: Client())

    result = x._run_xquik_search("mcp", 10, 30)

    assert result == {"error": "network unavailable", "items": []}
