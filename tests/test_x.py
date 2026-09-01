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


# ── Extract/parse internals ──────────────────────────────────────────────────


def test_extract_xquik_items_unknown_envelope_returns_empty() -> None:
    assert x._extract_xquik_items({"unknown": "envelope"}) == []


def test_extract_xquik_items_non_dict_payload_returns_empty() -> None:
    assert x._extract_xquik_items("not a dict") == []
    assert x._extract_xquik_items(42) == []
    assert x._extract_xquik_items(None) == []


def test_extract_xquik_items_data_non_dict_returns_empty() -> None:
    assert x._extract_xquik_items({"data": "scalar"}) == []


def test_dict_or_empty_coerces_non_dict() -> None:
    assert x._dict_or_empty("str") == {}
    assert x._dict_or_empty(123) == {}
    assert x._dict_or_empty(None) == {}
    assert x._dict_or_empty({"a": 1}) == {"a": 1}


def test_first_string_all_empty_returns_empty() -> None:
    assert x._first_string("", "   ", None, "") == ""


def test_first_string_picks_first_nonempty() -> None:
    assert x._first_string("", "  ", "hello", "world") == "hello"


def test_safe_int_non_convertible_returns_none() -> None:
    assert x._safe_int("abc") is None
    assert x._safe_int("12.5") is None
    assert x._safe_int(None) is None
    assert x._safe_int(7) == 7
    assert x._safe_int("42") == 42


def test_parse_item_non_dict_tweet_returns_none() -> None:
    assert x._parse_item("not a dict", 0, "q") is None
    assert x._parse_item(None, 0, "q") is None
    assert x._parse_item([], 0, "q") is None


def test_parse_item_missing_url_returns_none() -> None:
    tweet: dict = {"id": "1", "text": "hello"}
    assert x._parse_item(tweet, 0, "q") is None


def test_parse_item_invalid_date_returns_none_date() -> None:
    tweet: dict = {
        "id": "1",
        "text": "hello",
        "url": "https://x.com/u/status/1",
        "created_at": "not-a-date",
    }
    item = x._parse_item(tweet, 0, "q")
    assert item is not None
    assert item["date"] is None


def test_parse_item_valid_shape() -> None:
    tweet: dict = {
        "id": "99",
        "text": "hello world",
        "url": "https://x.com/u/status/99",
        "created_at": "Mon Jan 01 10:00:00 +0000 2024",
        "likeCount": 5,
        "author": {"username": "alice"},
    }
    item = x._parse_item(tweet, 0, "q")
    assert item is not None
    assert item["id"] == "X1"
    assert item["author_handle"] == "alice"
    assert item["date"] == "2024-01-01"
    assert item["engagement"]["likes"] == 5
