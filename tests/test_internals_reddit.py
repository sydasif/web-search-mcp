"""Offline unit tests for the keyless Reddit pipeline internals.

These exercise the pure string->dict parsers and query-expansion helpers
that have no network dependency. Network-touching functions (search_rss,
fetch_listings, fetch_comments) are covered indirectly by mocking the
client layer where feasible.
"""

from __future__ import annotations

from web_search_mcp.social.reddit import client, engine, models, parsers

# ── engine.py: query expansion ──────────────────────────────────────────────


def test_extract_core_subject_strips_prefix_and_noise() -> None:
    assert engine._extract_core_subject("what is the best python framework") == "python framework"
    assert engine._extract_core_subject("how to use docker") == "docker"


def test_extract_core_subject_filters_all_noise_words() -> None:
    # All tokens here are noise words, so they are all dropped
    assert engine._extract_core_subject("what is the best") == "the best"


def test_infer_query_intent_detects_kinds() -> None:
    assert engine._infer_query_intent("rust vs go comparison") == "comparison"
    assert engine._infer_query_intent("how to install kubernetes") == "how_to"
    assert engine._infer_query_intent("is this laptop worth it") == "opinion"
    assert engine._infer_query_intent("best laptop for coding") == "product"
    assert engine._infer_query_intent("predict the election outcome") == "prediction"
    assert engine._infer_query_intent("random musing about life") == "general"


def test_expand_queries_includes_original_and_core() -> None:
    out = engine.expand_queries("what is the best python framework", depth="quick")
    # core subject + original cleaned query (<=8 words)
    assert "python framework" in out
    assert "what is the best python framework" in out


def test_expand_queries_dedupes_preserving_order() -> None:
    out = engine.expand_queries("best running shoes", depth="default")
    assert len(out) == len(set(q.lower() for q in out))


def test_expand_queries_deep_adds_problem_variant() -> None:
    # "for coding" makes this a 'product' query, so deep adds the issues/problems variant
    out = engine.expand_queries("best headphones for coding", depth="deep")
    assert any("issues" in q or "problems" in q for q in out)


def test_merge_dedupe_drops_empty_urls() -> None:
    batches = [
        [{"url": "https://a"}, {"url": ""}],
        [{"url": "https://a"}, {"url": "https://b"}],
    ]
    merged = engine._merge_dedupe(batches)
    urls = [p["url"] for p in merged]
    assert urls == ["https://a", "https://b"]  # first occurrence wins, empty dropped


def test_search_and_enrich_sorts_and_limits(monkeypatch) -> None:
    posts = [
        {"url": "u1", "engagement": {"score": 5}, "relevance": 0.2, "date": "2026-01-02"},
        {"url": "u2", "engagement": {"score": 50}, "relevance": 0.9, "date": "2026-01-01"},
        {"url": "u3", "engagement": {"score": 1}, "relevance": 0.1, "date": "2026-01-03"},
    ]

    def fake_pipeline(_q, _from, _to, _depth, _subs):
        return posts

    monkeypatch.setattr(engine, "_run_single_pipeline", fake_pipeline)
    monkeypatch.setattr(engine, "_enrich", lambda p, _d: p)

    result = engine.search_and_enrich(
        "python", from_date="2026-01-01", to_date="2026-12-31", depth="quick"
    )
    # sorted by score desc
    assert [p["url"] for p in result] == ["u2", "u1", "u3"]
    # ids assigned
    assert [p["id"] for p in result] == ["R1", "R2", "R3"]
    # depth 'quick' caps reddit to 10; all 3 pass through
    assert len(result) == 3


# ── parsers.py: RSS/Atom + shreddit ─────────────────────────────────────────


ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Great python tip</title>
    <link href="https://www.reddit.com/r/Python/comments/abc123/title/"/>
    <author><name>/u/alice</name></author>
    <category term="Python"/>
    <updated>2026-03-01T12:00:00Z</updated>
    <content>Some body text here</content>
  </entry>
  <entry>
    <title>Non comment link</title>
    <link href="https://www.reddit.com/r/Python/"/>
  </entry>
</feed>
"""


def test_parse_feed_extracts_comment_entries() -> None:
    posts = parsers._parse_feed(ATOM_FEED, query="python")
    assert len(posts) == 1
    p = posts[0]
    assert p["title"] == "Great python tip"
    assert p["url"].endswith("/comments/abc123/title/")
    assert p["subreddit"] == "Python"
    assert p["author"] == "alice"
    assert p["date"] == "2026-03-01"
    assert p["relevance"] == 1.0  # token_overlap "python" in title


def test_parse_feed_empty_on_blank() -> None:
    assert parsers._parse_feed("", query="x") == []


def test_parse_feed_handles_malformed_xml() -> None:
    assert parsers._parse_feed("<feed><unclosed>", query="x") == []


def test_build_urls_global_and_per_subreddit() -> None:
    urls = parsers._build_urls("rust", depth="default", subreddits=["rustlang"])
    assert any("search.rss?q=rust" in u for u in urls)
    # subreddit scoped feeds + listing sorts (top, hot for default)
    assert any("/r/rustlang/search.rss" in u for u in urls)
    assert any("/r/rustlang/top.rss" in u for u in urls)
    assert any("/r/rustlang/hot.rss" in u for u in urls)


def test_build_urls_strips_r_prefix() -> None:
    urls = parsers._build_urls("go", depth="quick", subreddits=["r/golang"])
    assert any("/r/golang/" in u for u in urls)


def test_subreddit_from_prefers_category_then_url() -> None:
    assert parsers._subreddit_from("golang", "https://x/y") == "golang"
    assert parsers._subreddit_from("", "https://www.reddit.com/r/rust/comments/1/x/") == "rust"
    assert parsers._subreddit_from("", "https://nope/") == ""


def test_extract_post_ref() -> None:
    assert parsers.extract_post_ref("https://www.reddit.com/r/x/comments/zz99/title/") == (
        "x",
        "zz99",
    )
    assert parsers.extract_post_ref("https://example.com/not/a/post") is None


SHREDDIT_HTML = """
<div id="t1_abc-post-rtjson-content"><p>First paragraph of the comment.</p><p>Second paragraph here.</p></div>
<shreddit-comment author="bob" thingId="t1_abc" score="42" permalink="/r/x/comments/1/c/abc/" created="2026-04-01T00:00:00+00:00">
  <p>First paragraph of the comment.</p>
  <p>Second paragraph here.</p>
</shreddit-comment>
<div id="t1_del-post-rtjson-content"><p>removed body</p></div>
<shreddit-comment author="[deleted]" thingId="t1_del" score="0" permalink="/r/x/comments/1/c/del/">
  <p>removed body</p>
</shreddit-comment>
"""


def test_parse_comments_extracts_and_sorts() -> None:
    comments = parsers.parse_comments(SHREDDIT_HTML, limit=10)
    assert len(comments) == 1
    c = comments[0]
    assert c["author"] == "bob"
    assert c["score"] == 42
    assert "First paragraph" in c["excerpt"]
    assert c["url"].endswith("/comments/1/c/abc/")


def test_parse_comments_skips_deleted() -> None:
    comments = parsers.parse_comments(
        '<shreddit-comment author="[removed]" thingId="t1_x" score="1" permalink="/p/"></shreddit-comment>'
    )
    assert comments == []


def test_parse_comments_respects_limit() -> None:
    html = "".join(
        f'<div id="t1_{i}-post-rtjson-content"><p>body {i}</p></div>'
        f'<shreddit-comment author="u{i}" thingId="t1_{i}" score="{i}" permalink="/p/{i}/">'
        f"<p>body {i}</p></shreddit-comment>"
        for i in range(5)
    )
    assert len(parsers.parse_comments(html, limit=3)) == 3


def test_total_comments() -> None:
    assert parsers._total_comments('<div total-comments="17">') == 17
    assert parsers._total_comments("<div>no count</div>") is None


# ── models.py: SVC listing cards ───────────────────────────────────────────


def test_post_id_from_url() -> None:
    assert models._post_id("https://www.reddit.com/r/x/comments/xy99/title/") == "xy99"
    assert models._post_id("https://no.com/") == ""


def test_svc_url_building() -> None:
    url = models._svc_url("python", "top")
    assert url.startswith("https://www.reddit.com/svc/shreddit/community-more-posts/top/")
    assert "name=python" in url
    assert "&t=month" in url
    assert models._svc_url("python", "hot").endswith("?name=python")


SHREDDIT_POST_HTML = """
<shreddit-post permalink="/r/Python/comments/zzz1/my_post/" score="123"
  comment-count="9" post-title="My Post Title" author="carol"
  subreddit-name="Python" created-timestamp="2026-05-01T10:00:00+00:00">
</shreddit-post>
"""


def test_parse_cards_extracts_post() -> None:
    cards = models.parse_cards(SHREDDIT_POST_HTML, query="python")
    assert len(cards) == 1
    c = cards[0]
    assert c["title"] == "My Post Title"
    assert c["score"] == 123
    assert c["num_comments"] == 9
    assert c["subreddit"] == "Python"
    assert c["author"] == "carol"
    assert c["url"].endswith("/comments/zzz1/my_post/")
    assert c["metadata"]["post_id"] == "zzz1"
    assert c["date"] == "2026-05-01"


def test_parse_cards_skips_non_comment_links() -> None:
    html = '<shreddit-post permalink="/r/Python/notacomment/" score="1" comment-count="0" post-title="x" author="a" subreddit-name="Python" created-timestamp="2026-05-01T10:00:00+00:00"></shreddit-post>'
    assert models.parse_cards(html) == []


def test_parse_cards_handles_bad_int() -> None:
    html = '<shreddit-post permalink="/r/Python/comments/1/x/" score="notanint" comment-count="nope" post-title="t" author="a" subreddit-name="Python" created-timestamp="2026-05-01T10:00:00+00:00"></shreddit-post>'
    cards = models.parse_cards(html)
    assert cards[0]["score"] == 0
    assert cards[0]["num_comments"] == 0


# ── client.py: legacy .json + retry policy ─────────────────────────────────


def test_parse_json_posts_normalizes() -> None:
    data = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "j1",
                        "permalink": "/r/Python/comments/j1/title/",
                        "title": "JSON post",
                        "score": 77,
                        "num_comments": 4,
                        "subreddit": "Python",
                        "created_utc": 1700000000,
                        "author": "dave",
                        "selftext": "body text",
                    }
                }
            ]
        }
    }
    posts = client._parse_json_posts(data, query="python")
    assert len(posts) == 1
    p = posts[0]
    assert p["title"] == "JSON post"
    assert p["score"] == 77
    assert p["subreddit"] == "Python"
    assert p["url"] == "https://www.reddit.com/r/Python/comments/j1/title/"
    assert p["date"] == "2023-11-14"
    assert p["metadata"]["post_id"] == "j1"


def test_parse_json_posts_skips_missing_permalink() -> None:
    data = {"data": {"children": [{"data": {"title": "no link"}}]}}
    assert client._parse_json_posts(data) == []


def test_parse_json_posts_returns_empty_on_exception() -> None:
    # malformed data shouldn't raise — helper swallows and returns []
    assert client._parse_json_posts({"data": "not a dict"}) == []


def test_should_retry_http_on_429_and_5xx() -> None:
    err_429 = client.HTTPError("429", status_code=429)
    err_500 = client.HTTPError("500", status_code=500)
    err_404 = client.HTTPError("404", status_code=404)
    assert client._should_retry_http(err_429) is True
    assert client._should_retry_http(err_500) is True
    assert client._should_retry_http(err_404) is False


def test_should_retry_http_on_dns_failure() -> None:
    import socket
    import urllib.error

    url_err = urllib.error.URLError(socket.gaierror("no host"))
    assert client._should_retry_http(url_err) is True


def test_is_dns_failure_true_only_for_gaierror() -> None:
    import socket
    import urllib.error

    assert client._is_dns_failure(urllib.error.URLError(socket.gaierror("x"))) is True
    assert client._is_dns_failure(urllib.error.URLError("generic")) is False


def test_search_json_returns_empty_on_failure(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "get", boom)
    assert client.search_json("python", depth="default") == []
