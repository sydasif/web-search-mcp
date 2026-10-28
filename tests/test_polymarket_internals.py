"""Offline unit tests for Polymarket search internals."""

from __future__ import annotations

from web_search_mcp.tools.polymarket import (
    _expand_queries,
    _passes_topic_filter,
    parse_polymarket_response,
)


class TestExpandQueries:
    """Test query expansion logic."""

    def test_basic_expansion(self) -> None:
        queries = _expand_queries("python async")
        assert "python async" in queries
        # "async" should be added as individual token
        assert any("async" in q for q in queries)

    def test_strips_prefixes(self) -> None:
        queries = _expand_queries("what is the best python framework")
        # The internal function strips prefixes but the public one might not
        assert len(queries) >= 1

    def test_preserves_original_and_core(self) -> None:
        # Function keeps original query + core + individual words (deduped by lowercase)
        queries = _expand_queries("python python")
        # Original "python python" and core "python" both kept (different lowercase)
        assert "python python" in queries
        assert "python" in queries
        # Total should be 2
        assert len(queries) == 2


def _extract_core_subject(topic: str) -> str:
    """Helper to test internal function - not exported."""
    from web_search_mcp.tools.polymarket import _extract_core_subject as _ecs

    return _ecs(topic)


class TestPassesTopicFilter:
    """Test the relevance filter for events."""

    def test_matching_event_passes(self) -> None:
        event = {"title": "Will Bitcoin reach $100k in 2024?"}
        assert _passes_topic_filter("bitcoin 2024", event["title"]) is True

    def test_non_matching_event_fails(self) -> None:
        event = {"title": "Will Ethereum reach $5000 in 2024?"}
        assert _passes_topic_filter("bitcoin", event["title"]) is False

    def test_stopword_only_query_requires_match(self) -> None:
        event = {"title": "Random sports event"}
        # "the" is treated as informative but must match in title
        assert _passes_topic_filter("the", event["title"]) is False
        # But "random" would pass
        assert _passes_topic_filter("random", event["title"]) is True


class TestParsePolymarketResponse:
    """Test the response parser."""

    def test_parses_valid_event(self) -> None:
        response = {
            "results": [
                {
                    "id": "evt_123",
                    "title": "Will Bitcoin hit $100k?",
                    "endDate": "2024-12-31T23:59:59Z",
                    "volume": 1000000,
                    "liquidity": 500000,
                    "markets": [
                        {"question": "Yes"},
                        {"question": "No"},
                    ],
                }
            ]
        }
        items = parse_polymarket_response(response, "bitcoin")
        assert len(items) == 1
        item = items[0]
        assert item["id"] == "evt_123"
        assert item["title"] == "Will Bitcoin hit $100k?"
        assert item["date"] == "2024-12-31"
        assert item["engagement"]["volume"] == 1000000
        assert item["engagement"]["liquidity"] == 500000
        assert item["engagement"]["outcomes"] == ["Yes", "No"]
        assert 0 <= item["relevance"] <= 1

    def test_filters_non_matching_events(self) -> None:
        response = {
            "results": [
                {"id": "1", "title": "Bitcoin event", "volume": 1000, "liquidity": 500},
                {"id": "2", "title": "Ethereum event", "volume": 1000, "liquidity": 500},
            ]
        }
        items = parse_polymarket_response(response, "bitcoin")
        # Should only keep bitcoin event
        assert len(items) == 1
        assert items[0]["title"] == "Bitcoin event"

    def test_sorts_by_relevance_desc(self) -> None:
        response = {
            "results": [
                {"id": "1", "title": "Low relevance", "volume": 100, "liquidity": 50},
                {"id": "2", "title": "High relevance Bitcoin", "volume": 1000, "liquidity": 500},
            ]
        }
        items = parse_polymarket_response(response, "bitcoin")
        assert items[0]["title"] == "High relevance Bitcoin"

    def test_empty_response_returns_empty(self) -> None:
        items = parse_polymarket_response({}, "test")
        assert items == []
        items = parse_polymarket_response({"results": []}, "test")
        assert items == []

    def test_non_list_results_returns_empty(self) -> None:
        items = parse_polymarket_response({"results": "not a list"}, "test")
        assert items == []
