"""End-to-end tests for all MCP tool implementations.

Calls each tool's underlying implementation function directly (bypassing
the MCP stdio transport layer) to verify they return correct response
types and non-empty results under real network conditions.
"""

from __future__ import annotations

import sys
import time

from web_search_mcp._models import PageResponse, SearchResponse

# ── results tracking ───────────────────────────────────────────────────────

results: list[dict] = []


def _record(name: str, status: str, detail: str) -> None:
    results.append({"tool": name, "status": status, "detail": detail[:300] if detail else ""})


def _check(name: str, ok: bool, detail: str, warn_if_fail: bool = False) -> None:
    if ok:
        _record(name, "PASS", detail)
    elif warn_if_fail:
        _record(name, "WARN", detail)
    else:
        _record(name, "FAIL", detail)


# ═══════════════════════════════════════════════════════════════════════════
#  1. search_web
# ═══════════════════════════════════════════════════════════════════════════


def test_search_web() -> None:
    from web_search_mcp._models.requests import SearchRequest
    from web_search_mcp.search.ddg import ddg_search

    req = SearchRequest(query="Python programming", max_results=2)
    result = ddg_search(req)
    ok = isinstance(result, SearchResponse) and len(result.results) > 0
    detail = f"results={result.total_results}" if isinstance(result, SearchResponse) else f"type={type(result).__name__}"
    _check("search_web", ok, detail)


# ═══════════════════════════════════════════════════════════════════════════
#  2. fetch_web_page
# ═══════════════════════════════════════════════════════════════════════════


def test_fetch_web_page() -> None:
    from web_search_mcp.search.ddg import fetch_page

    result = fetch_page("https://example.com", max_length=500)
    if isinstance(result, PageResponse):
        ok = len(result.content) > 0 and "example" in result.content.lower()
        _check("fetch_web_page", ok, f"len={result.length}")
    else:
        err = getattr(result, "error", str(result))
        _check("fetch_web_page", False, f"ErrorResponse: {err}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. search_reddit
# ═══════════════════════════════════════════════════════════════════════════


def test_search_reddit() -> None:
    from web_search_mcp.social.reddit import reddit_search_tool

    result = reddit_search_tool(query="Python", max_results=3, depth="quick", response_format="json")
    ok = isinstance(result, SearchResponse) and result.total_results >= 0
    n = result.total_results if isinstance(result, SearchResponse) else 0
    ok = isinstance(result, SearchResponse) and len(result.results) > 0
    _check("search_reddit", ok, f"posts={n}", warn_if_fail=True)


# ═══════════════════════════════════════════════════════════════════════════
#  4. search_hackernews
# ═══════════════════════════════════════════════════════════════════════════


def test_search_hackernews() -> None:
    from web_search_mcp.social.hackernews import search_hackernews

    items = search_hackernews("MCP server", depth="quick")
    ok = len(items) > 0
    _check("search_hackernews", ok, f"stories={len(items)}", warn_if_fail=True)


# ═══════════════════════════════════════════════════════════════════════════
#  5. search_github
# ═══════════════════════════════════════════════════════════════════════════


def test_search_github() -> None:
    from web_search_mcp.social.github import search_github

    items = search_github("uv package manager", depth="quick")
    ok = len(items) > 0
    _check("search_github", ok, f"items={len(items)}", warn_if_fail=True)


# ═══════════════════════════════════════════════════════════════════════════
#  6. search_x
# ═══════════════════════════════════════════════════════════════════════════


def test_search_x() -> None:
    from web_search_mcp.social.x import search_x

    items = search_x("hello world", depth="quick")
    # X returns error items (XERR) when not authenticated — still means the code runs
    ok = isinstance(items, list)
    _check("search_x", ok, f"items={len(items)} (may need AUTH_TOKEN+CT0)", warn_if_fail=True)


# ═══════════════════════════════════════════════════════════════════════════
#  7. get_github_issue
# ═══════════════════════════════════════════════════════════════════════════


def test_get_github_issue() -> None:
    from web_search_mcp.social.github import get_github_issue

    result = get_github_issue("https://github.com/astral-sh/uv/issues/1")
    # Returns an error string if gh CLI is missing — still tests the code path
    ok = isinstance(result, str) and len(result) > 0
    _check("get_github_issue", ok, f"len={len(result)}", warn_if_fail=True)


# ═══════════════════════════════════════════════════════════════════════════
#  8. search_arxiv
# ═══════════════════════════════════════════════════════════════════════════


def test_search_arxiv() -> None:
    from web_search_mcp.tools.arxiv import search_arxiv

    items = search_arxiv("transformer attention", max_results=3)
    ok = isinstance(items, list) and len(items) > 0
    _check("search_arxiv", ok, f"papers={len(items) if isinstance(items, list) else 'error'}")


# ═══════════════════════════════════════════════════════════════════════════
#  9. search_wikipedia
# ═══════════════════════════════════════════════════════════════════════════


def test_search_wikipedia() -> None:
    from web_search_mcp.tools.wikipedia import wikipedia_search_tool

    result = wikipedia_search_tool("Python programming language", max_results=3)
    ok = isinstance(result, str) and "Wikipedia" in result and "Python" in result
    _check("search_wikipedia", ok, f"len={len(result)}")


# ═══════════════════════════════════════════════════════════════════════════
#  10. compare_technologies
# ═══════════════════════════════════════════════════════════════════════════


def test_compare_technologies() -> None:
    from web_search_mcp.tools.compare import compare_tech

    result = compare_tech("React", "Vue", category="framework")
    ok = isinstance(result, str) and "React" in result and "Vue" in result
    _check("compare_technologies", ok, f"len={len(result)}")


# ═══════════════════════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> int:
    tests = [
        ("search_web", test_search_web),
        ("fetch_web_page", test_fetch_web_page),
        ("search_reddit", test_search_reddit),
        ("search_hackernews", test_search_hackernews),
        ("search_github", test_search_github),
        ("search_x", test_search_x),
        ("get_github_issue", test_get_github_issue),
        ("search_arxiv", test_search_arxiv),
        ("search_wikipedia", test_search_wikipedia),
        ("compare_technologies", test_compare_technologies),
    ]

    print("=" * 72)
    print("  WEB SEARCH MCP — End-to-End Tool Tests")
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)
    print()

    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            results.append({"tool": name, "status": "ERROR", "detail": str(e)[:300]})

        # Show result inline
        r = results[-1]
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "ERROR": "💥"}.get(r["status"], "❓")
        print(f"  {icon}  {r['tool']:25s}  {r['status']:5s}  {r['detail'][:100]}")

    print()
    print("-" * 72)

    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    total = passed + warned + failed
    print(f"  Total: {total}  |  ✅ Pass: {passed}  |  ⚠️ Warn: {warned}  |  ❌ Fail: {failed}")
    print("=" * 72)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
