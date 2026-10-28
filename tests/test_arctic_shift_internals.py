"""Offline unit tests for Arctic-Shift internals."""

from __future__ import annotations

from web_search_mcp.social.reddit.arctic_shift import _parse_score_rows


class TestParseScoreRows:
    """Test the pure score row parser."""

    def test_parses_valid_rows(self) -> None:
        rows = [
            {"id": "t3_abc123", "score": 42, "num_comments": 5},
            {"id": "def456", "score": "10", "num_comments": "2"},  # string coercion
            {"id": "t3_ghi789", "score": 0, "num_comments": 0},
        ]
        result = _parse_score_rows(rows)
        assert result == {
            "abc123": {"score": 42, "num_comments": 5},
            "def456": {"score": 10, "num_comments": 2},
            "ghi789": {"score": 0, "num_comments": 0},
        }

    def test_strips_t3_prefix(self) -> None:
        rows = [{"id": "t3_xyz", "score": 1, "num_comments": 1}]
        result = _parse_score_rows(rows)
        assert "xyz" in result
        assert "t3_xyz" not in result

    def test_skips_non_dict_rows(self) -> None:
        rows = [{"id": "t3_a", "score": 1}, "not a dict", None, 123]
        result = _parse_score_rows(rows)
        assert result == {"a": {"score": 1, "num_comments": 0}}

    def test_skips_missing_id(self) -> None:
        rows = [{"score": 10, "num_comments": 2}, {"id": "t3_x", "score": 5}]
        result = _parse_score_rows(rows)
        assert result == {"x": {"score": 5, "num_comments": 0}}

    def test_skips_non_numeric_score(self) -> None:
        rows = [
            {"id": "t3_a", "score": "bad", "num_comments": 1},
            {"id": "t3_b", "score": 2, "num_comments": 3},
        ]
        result = _parse_score_rows(rows)
        assert result == {"b": {"score": 2, "num_comments": 3}}

    def test_skips_non_numeric_num_comments(self) -> None:
        rows = [{"id": "t3_a", "score": 5, "num_comments": "bad"}]
        result = _parse_score_rows(rows)
        assert result == {}

    def test_empty_list_returns_empty(self) -> None:
        assert _parse_score_rows([]) == {}

    def test_handles_none_values(self) -> None:
        rows = [{"id": "t3_a", "score": None, "num_comments": None}]
        result = _parse_score_rows(rows)
        assert result == {"a": {"score": 0, "num_comments": 0}}
