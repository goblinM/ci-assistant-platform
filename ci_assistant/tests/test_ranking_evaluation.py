import json
from pathlib import Path

import pytest

from ci_assistant.evaluation.ranking import (
    compare_rankings,
    evaluate_ranking,
    reciprocal_rank,
)


def test_ranking_metrics_compare_hybrid_and_reranker() -> None:
    """验证固定用例可量化 Reranker 相对 Hybrid 的排序改善。"""
    cases = json.loads(
        (
            Path(__file__).parents[1] / "ranking_evaluation_cases.json"
        ).read_text(encoding="utf-8")
    )

    result = compare_rankings(cases)

    assert result["hybrid"]["case_count"] == 3
    assert result["reranked"]["recall_at_1"] == 1.0
    assert result["reranked"]["mrr"] > result["hybrid"]["mrr"]
    assert result["delta"]["recall_at_1"] > 0


def test_ranking_evaluation_rejects_missing_expectations() -> None:
    """验证缺少期望文档的用例不会产生虚假指标。"""
    with pytest.raises(ValueError, match="expected_ids"):
        evaluate_ranking(
            [{"id": "invalid", "hybrid": [{"id": "doc"}]}],
            strategy="hybrid",
        )


def test_reciprocal_rank_returns_zero_for_miss() -> None:
    """验证完全未命中时 MRR 单项为零。"""
    assert reciprocal_rank(["a", "b"], {"c"}) == 0.0
