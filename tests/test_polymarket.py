"""Tests for Polymarket search module."""

import unittest
from unittest.mock import patch, MagicMock

from web_search_mcp.polymarket import (
    search_polymarket,
    _extract_core_subject,
    _expand_queries,
    _passes_topic_filter,
    _parse_outcome_prices,
    _format_price_movement,
)


class TestHelpers(unittest.TestCase):
    """Tests for helper functions."""

    def test_extract_core_subject_strips_noise(self):
        assert _extract_core_subject("what are people saying about NVIDIA") == "NVIDIA"
        assert _extract_core_subject("last 7 days Fed rate cut") == "Fed rate cut"
        assert _extract_core_subject("tell me about Claude") == "Claude"

    def test_expand_queries_captures_individual_words(self):
        queries = _expand_queries("Fed rate cut")
        assert len(queries) >= 2
        assert any("Fed" in q for q in queries)

    def test_expand_queries_dedupes(self):
        queries = _expand_queries("NVIDIA NVIDIA")
        assert len(queries) == len(set(q.lower() for q in queries))

    def test_expand_queries_max_six(self):
        queries = _expand_queries("a b c d e f g h i j")
        assert len(queries) <= 6

    def test_passes_topic_filter_exact_match(self):
        assert _passes_topic_filter("NVIDIA", "Will NVIDIA hit $5T?") is True

    def test_passes_topic_filter_no_match(self):
        assert _passes_topic_filter("NVIDIA", "Will Apple release a new iPhone?") is False

    def test_passes_topic_filter_short_topic(self):
        # Single informative word — 1 match is enough
        assert _passes_topic_filter("Claude", "Claude 5 release date") is True

    def test_passes_topic_filter_all_generic(self):
        # All generic words — should always pass
        assert _passes_topic_filter("the team win", "Any event") is True

    def test_parse_outcome_prices_from_json_strings(self):
        market = {
            "outcomes": '["Yes", "No"]',
            "outcomePrices": "[0.65, 0.35]",
        }
        result = _parse_outcome_prices(market)
        assert result == [("Yes", 0.65), ("No", 0.35)]

    def test_parse_outcome_prices_from_lists(self):
        market = {"outcomes": ["Up", "Down"], "outcomePrices": [0.7, 0.3]}
        result = _parse_outcome_prices(market)
        assert result == [("Up", 0.7), ("Down", 0.3)]

    def test_parse_outcome_prices_missing(self):
        assert _parse_outcome_prices({}) == []

    def test_parse_outcome_prices_invalid_json(self):
        assert _parse_outcome_prices({"outcomes": "bad", "outcomePrices": "bad"}) == []

    def test_format_price_movement_big_move(self):
        market = {
            "oneDayPriceChange": 0.15,
            "oneWeekPriceChange": 0.02,
            "oneMonthPriceChange": 0.01,
        }
        result = _format_price_movement(market)
        assert "up" in result
        assert "15.0%" in result

    def test_format_price_movement_small_move(self):
        market = {
            "oneDayPriceChange": 0.001,
            "oneWeekPriceChange": 0.002,
            "oneMonthPriceChange": 0.001,
        }
        assert _format_price_movement(market) is None

    def test_format_price_movement_down(self):
        market = {"oneDayPriceChange": -0.10, "oneWeekPriceChange": 0, "oneMonthPriceChange": 0}
        result = _format_price_movement(market)
        assert "down" in result


class TestSearch(unittest.TestCase):
    """Tests for search_polymarket."""

    @patch("web_search_mcp.polymarket.httpx.get")
    def test_search_returns_items(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "events": [
                {
                    "id": "evt-1",
                    "title": "Will NVIDIA hit $5T?",
                    "slug": "nvidia-5t",
                    "active": True,
                    "closed": False,
                    "markets": [
                        {
                            "question": "Will NVIDIA hit $5T?",
                            "active": True,
                            "closed": False,
                            "liquidity": 50000,
                            "volume": 100000,
                            "outcomes": '["Yes", "No"]',
                            "outcomePrices": "[0.35, 0.65]",
                        }
                    ],
                    "volume1mo": 100000,
                    "liquidity": 50000,
                    "updatedAt": "2026-06-08T12:00:00Z",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        items = search_polymarket("NVIDIA", depth="quick")
        assert len(items) >= 1
        assert items[0]["title"] == "Will NVIDIA hit $5T?"

    @patch("web_search_mcp.polymarket.httpx.get")
    def test_search_filters_closed_events(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "events": [
                {
                    "id": "1",
                    "title": "Closed event",
                    "closed": True,
                    "active": False,
                    "markets": [],
                },
                {
                    "id": "2",
                    "title": "Open event",
                    "closed": False,
                    "active": True,
                    "markets": [
                        {
                            "active": True,
                            "closed": False,
                            "liquidity": 100,
                            "volume": 500,
                            "outcomes": '["Yes", "No"]',
                            "outcomePrices": "[0.5, 0.5]",
                        }
                    ],
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        items = search_polymarket("test")
        titles = [i["title"] for i in items]
        assert "Closed event" not in titles

    @patch("web_search_mcp.polymarket.httpx.get")
    def test_search_http_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        items = search_polymarket("test")
        assert items == []


if __name__ == "__main__":
    unittest.main()
