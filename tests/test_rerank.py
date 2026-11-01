"""Unit tests for rerank tool."""

import pytest

from web_search_mcp.tools.rerank import rerank_documents


class TestRerankDocuments:
    """Tests for rerank_documents function."""

    def test_exact_match_scores_one(self):
        """Exact token match should score 1.0 before length penalty; with penalty it's >= 0.5."""
        # Use a document >50 chars to avoid length penalty
        long_doc = "python async guide with detailed explanation and examples for developers"
        result = rerank_documents("python async", [long_doc])
        # Query has 2 tokens, doc has both -> intersection=2, score=2/2=1.0
        # Doc length > 50, no penalty
        assert result[0]["score"] == 1.0
        assert result[0]["document"] == long_doc
        assert result[0]["index"] == 0

    def test_partial_token_overlap(self):
        """Partial token overlap should score between 0 and 1."""
        # Use docs >50 chars to avoid length penalty
        docs = [
            "python guide with detailed explanation and examples for developers",  # "python" only
            "async rust guide with detailed explanation and examples for developers",  # "async" only
            "java sync guide with detailed explanation and examples for developers",  # no overlap
        ]
        result = rerank_documents("python async", docs)
        scores = [r["score"] for r in result]
        # "python guide" has 1/2 tokens = 0.5
        # "async rust" has 1/2 tokens = 0.5
        # "java sync" has 0/2 tokens = 0.0
        assert scores[0] == 0.5
        assert scores[1] == 0.5
        assert scores[2] == 0.0

    def test_empty_query_returns_zero_scores(self):
        """Empty query should return all scores as 0.0."""
        result = rerank_documents("", ["doc1", "doc2", "doc3"])
        assert all(r["score"] == 0.0 for r in result)
        assert len(result) == 3
        assert [r["index"] for r in result] == [0, 1, 2]

    def test_whitespace_query_returns_zero_scores(self):
        """Whitespace-only query should return all scores as 0.0."""
        result = rerank_documents("   ", ["doc1", "doc2"])
        assert all(r["score"] == 0.0 for r in result)

    def test_empty_documents_returns_empty_list(self):
        """Empty documents list should return empty list."""
        result = rerank_documents("query", [])
        assert result == []

    def test_top_n_truncation(self):
        """top_n should truncate results."""
        docs = [
            "python async guide with detailed explanation and examples for developers",
            "rust async guide with detailed explanation and examples for developers",
            "python sync guide with detailed explanation and examples for developers",
            "java thread guide with detailed explanation and examples for developers",
        ]
        result = rerank_documents("python async", docs, top_n=2)
        assert len(result) == 2
        assert result[0]["score"] >= result[1]["score"]

    def test_top_n_zero_returns_empty(self):
        """top_n <= 0 should return empty list."""
        result = rerank_documents("query", ["doc1", "doc2"], top_n=0)
        assert result == []
        result = rerank_documents("query", ["doc1", "doc2"], top_n=-1)
        assert result == []

    def test_original_index_preserved(self):
        """Original index should be preserved in output."""
        docs = [
            "rust async guide with detailed explanation and examples for developers",
            "python async guide with detailed explanation and examples for developers",
            "java sync guide with detailed explanation and examples for developers",
        ]
        result = rerank_documents("python async", docs)
        # "python async guide" was at index 1, should be first after sorting
        assert result[0]["index"] == 1
        assert result[0]["document"] == "python async guide with detailed explanation and examples for developers"

    def test_length_penalty_short_document(self):
        """Very short documents should be penalized (min 0.5 multiplier)."""
        # Short doc (<50 chars) gets penalty of length/50
        short_doc = "py async"  # 8 chars -> penalty 8/50 = 0.16, floor 0.5
        long_doc = "python asyncio guide with detailed explanation and examples for developers"  # >50 chars

        result = rerank_documents("python async", [short_doc, long_doc])
        short_result = next(r for r in result if r["document"] == short_doc)
        long_result = next(r for r in result if r["document"] == long_doc)
        # Short doc should have lower score due to penalty
        assert short_result["score"] < long_result["score"]
        # Short doc max score is 0.5 due to penalty floor
        assert short_result["score"] <= 0.5

    def test_length_penalty_long_document(self):
        """Very long documents should be penalized."""
        normal_doc = "python async guide with detailed explanation and examples for developers"
        # Create a very long doc (>5000 chars)
        long_doc = "python async " + "x" * 6000

        result = rerank_documents("python async", [normal_doc, long_doc])
        normal_result = next(r for r in result if r["document"] == normal_doc)
        long_result = next(r for r in result if r["document"] == long_doc)
        # Both have same token overlap (1.0), but long doc gets penalty
        # Normal doc > 50 chars, no penalty -> 1.0
        # Long doc gets penalty -> < 1.0
        assert normal_result["score"] == 1.0
        assert long_result["score"] < 1.0

    def test_malformed_inputs_none_in_documents(self):
        """None in documents list should be handled gracefully."""
        result = rerank_documents("python", ["valid doc with explanation here", None, "another doc with explanation"])
        assert len(result) == 3
        # None entries get score 0.0
        none_result = next(r for r in result if r["document"] == "")
        assert none_result["score"] == 0.0

    def test_malformed_inputs_non_string_in_documents(self):
        """Non-string in documents list should be handled gracefully."""
        result = rerank_documents("python", ["valid doc with explanation here", 123, "another doc with explanation"])
        assert len(result) == 3
        # Non-string gets converted to string and scored
        num_result = next(r for r in result if r["document"] == "123")
        assert num_result["score"] == 0.0  # "123" has no token overlap with "python"

    def test_sorting_descending_by_score(self):
        """Results should be sorted descending by score."""
        docs = [
            "java sync guide with detailed explanation and examples for developers",
            "python guide with detailed explanation and examples for developers",
            "python async programming guide with examples for developers",
        ]
        result = rerank_documents("python async", docs)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_case_insensitive_matching(self):
        """Matching should be case insensitive."""
        long_doc = "PYTHON ASYNC GUIDE WITH DETAILED EXPLANATION AND EXAMPLES FOR DEVELOPERS"
        result_lower = rerank_documents("python async", [long_doc])
        result_upper = rerank_documents("PYTHON ASYNC", ["python async guide with detailed explanation and examples"])
        # Both should score 1.0 (doc > 50 chars, no penalty)
        assert result_lower[0]["score"] == result_upper[0]["score"] == 1.0

    def test_duplicate_documents(self):
        """Duplicate documents should be deduplicated (keeping highest-scored)."""
        docs = [
            "python async guide with details and examples for developers",
            "python async guide with details and examples for developers",
            "rust async guide with details and examples for developers",
        ]
        result = rerank_documents("python async", docs)
        assert len(result) == 2
        # First "python async" entry (index 0) kept, duplicate (index 1) removed
        assert result[0]["index"] == 0
        assert result[0]["score"] == 1.0
        assert result[1]["index"] == 2

    def test_deduplicate_disabled(self):
        """deduplicate=False should preserve all documents including duplicates."""
        docs = [
            "python async guide with details and examples for developers",
            "python async guide with details and examples for developers",
            "rust async guide with details and examples for developers",
        ]
        result = rerank_documents("python async", docs, deduplicate=False)
        assert len(result) == 3
        python_results = [r for r in result if "python async" in r["document"]]
        assert len(python_results) == 2
        assert all(r["score"] == 1.0 for r in python_results)
        assert {r["index"] for r in python_results} == {0, 1}

    def test_top_n_greater_than_documents(self):
        """top_n greater than document count should return all documents."""
        docs = ["doc1 with explanation and details", "doc2 with explanation and details"]
        result = rerank_documents("query", docs, top_n=10)
        assert len(result) == 2
    def test_near_duplicate_documents(self):
        """Near-duplicate documents should be deduplicated."""
        docs = [
            "python async guide with details and examples for developers",
            "python async guide with details and examples for developer",  # 1 char diff
            "rust async guide completely different content here",
        ]
        result = rerank_documents("python async", docs)
        # The near-dup (index 1) should be removed
        indices = {r["index"] for r in result}
        assert 0 in indices
        assert 2 in indices

    def test_dedup_threshold_configurable(self):
        """dedup_threshold controls how aggressive dedup is."""
        docs = [
            "python async guide with details and examples for developers",
            "python async guide with details and examples for developer",
        ]
        # Very high threshold = less dedup
        result_strict = rerank_documents("python", docs, dedup_threshold=0.99)
        assert len(result_strict) == 2
        # Lower threshold = more dedup
        result_loose = rerank_documents("python", docs, dedup_threshold=0.5)
        assert len(result_loose) == 1

    def test_chunk_diversity_max_per_parent(self):
        """max_per_parent should limit chunks from same parent."""
        docs = [
            "python async chunk one with enough length for scoring",
            "python async chunk two with enough length for scoring",
            "python async chunk three with enough length for scoring",
            "rust async completely different topic for comparison",
        ]
        meta = [
            {"parent_id": "doc_a"},
            {"parent_id": "doc_a"},
            {"parent_id": "doc_a"},
            {"parent_id": "doc_b"},
        ]
        result = rerank_documents("python async", docs, documents_meta=meta, max_per_parent=1)
        # Only 1 chunk from doc_a + 1 from doc_b
        assert len(result) == 2
        parents = [r.get("parent_id") for r in result]
        assert "doc_a" in parents
        assert "doc_b" in parents

    def test_max_per_parent_zero_unlimited(self):
        """max_per_parent=0 should disable chunk diversity."""
        docs = [
            "python async chunk one with enough length for scoring",
            "python async chunk two with enough length for scoring",
        ]
        meta = [{"parent_id": "doc_a"}, {"parent_id": "doc_a"}]
        result = rerank_documents("python async", docs, documents_meta=meta, max_per_parent=0)
        assert len(result) == 2

    def test_metadata_engagement_boost(self):
        """Higher engagement should boost score."""
        docs = [
            "python guide with enough content to avoid length penalty here ok",
            "python guide with enough content to avoid length penalty here ok",
        ]
        meta_no_eng = [{"engagement": 0}, {"engagement": 0}]
        meta_high_eng = [{"engagement": 0}, {"engagement": 10000}]

        result_base = rerank_documents("async tutorial", docs, documents_meta=meta_no_eng, deduplicate=False)
        result_boosted = rerank_documents("async tutorial", docs, documents_meta=meta_high_eng, deduplicate=False)

        # Both docs same text, but doc 1 should score higher with engagement
        assert result_boosted[0]["index"] == 1
        assert result_boosted[0]["score"] > result_base[0]["score"]

    def test_metadata_freshness_boost(self):
        """Fresher documents should score higher."""
        docs = [
            "python guide with enough content to avoid length penalty here ok",
            "python guide with enough content to avoid length penalty here ok",
        ]
        meta = [{"freshness_days": 0}, {"freshness_days": 365}]
        result = rerank_documents("async tutorial", docs, documents_meta=meta, deduplicate=False)
        assert result[0]["index"] == 0  # Fresh doc wins
        assert result[0]["score"] > result[1]["score"]

    def test_metadata_authority_boost(self):
        """Higher authority should boost score."""
        docs = [
            "python guide with enough content to avoid length penalty here ok",
            "python guide with enough content to avoid length penalty here ok",
        ]
        meta = [{"authority": 1.0}, {"authority": 0.0}]
        result = rerank_documents("async tutorial", docs, documents_meta=meta, deduplicate=False)
        assert result[0]["index"] == 0
        assert result[0]["score"] > result[1]["score"]

    def test_custom_weights(self):
        """Custom weights should affect blending."""
        docs = ["python async guide", "rust async guide"]
        # All token weight, no neural
        result = rerank_documents(
            "python async", docs,
            backend="hybrid",
            weights={"token": 1.0, "neural": 0.0, "engagement": 0.0, "freshness": 0.0, "authority": 0.0, "custom": 0.0},
        )
        # python doc should score higher with pure token overlap
        assert result[0]["document"].startswith("python")

    def test_empty_query_with_metadata(self):
        """Empty query should still apply metadata boosts."""
        docs = [
            "some document with enough length to be valid here ok",
            "another document with enough length to be valid here",
        ]
        meta = [{"engagement": 10000}, {"engagement": 0}]
        result = rerank_documents("", docs, documents_meta=meta)
        assert result[0]["index"] == 0
        assert result[0]["score"] > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
