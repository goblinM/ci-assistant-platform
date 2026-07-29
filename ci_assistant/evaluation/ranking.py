from __future__ import annotations

from typing import Any


def recall_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """计算单条用例在 Top K 中是否命中期望文档。"""
    return float(bool(set(ranked_ids[:k]) & expected_ids))


def reciprocal_rank(ranked_ids: list[str], expected_ids: set[str]) -> float:
    """计算首个期望文档的倒数排名。"""
    for rank, document_id in enumerate(ranked_ids, start=1):
        if document_id in expected_ids:
            return 1.0 / rank
    return 0.0


def reference_precision_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """计算 Top K 引用中期望文档的占比。"""
    selected = ranked_ids[:k]
    if not selected:
        return 0.0
    return sum(item in expected_ids for item in selected) / len(selected)


def metadata_hit_rate_at_k(
    ranked: list[dict[str, Any]],
    expected_metadata: dict[str, Any],
    k: int,
) -> float:
    """计算 Top K 结果满足期望 Metadata 的比例。"""
    selected = ranked[:k]
    if not selected:
        return 0.0
    if not expected_metadata:
        return 1.0
    hits = sum(
        all(
            (item.get("metadata") or {}).get(key) == value
            for key, value in expected_metadata.items()
        )
        for item in selected
    )
    return hits / len(selected)


def evaluate_ranking(
    cases: list[dict[str, Any]],
    *,
    strategy: str,
) -> dict[str, float | int | str]:
    """汇总指定排序策略的 Recall、MRR、Metadata Hit 和引用精度。"""
    if not cases:
        raise ValueError("ranking evaluation requires at least one case")
    totals = {
        "recall_at_1": 0.0,
        "recall_at_3": 0.0,
        "mrr": 0.0,
        "metadata_hit_rate_at_3": 0.0,
        "reference_precision_at_3": 0.0,
    }
    for case in cases:
        ranked = case.get(strategy)
        if not isinstance(ranked, list):
            raise ValueError(f"case {case.get('id')} has no {strategy} ranking")
        expected_ids = {str(value) for value in case.get("expected_ids") or []}
        if not expected_ids:
            raise ValueError(f"case {case.get('id')} has no expected_ids")
        ranked_ids = [str(item["id"]) for item in ranked]
        totals["recall_at_1"] += recall_at_k(ranked_ids, expected_ids, 1)
        totals["recall_at_3"] += recall_at_k(ranked_ids, expected_ids, 3)
        totals["mrr"] += reciprocal_rank(ranked_ids, expected_ids)
        totals["metadata_hit_rate_at_3"] += metadata_hit_rate_at_k(
            ranked,
            case.get("expected_metadata") or {},
            3,
        )
        totals["reference_precision_at_3"] += reference_precision_at_k(
            ranked_ids,
            expected_ids,
            3,
        )
    count = len(cases)
    return {
        "strategy": strategy,
        "case_count": count,
        **{name: value / count for name, value in totals.items()},
    }


def compare_rankings(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """比较固定用例中的 Hybrid 与 Reranked 离线指标。"""
    hybrid = evaluate_ranking(cases, strategy="hybrid")
    reranked = evaluate_ranking(cases, strategy="reranked")
    deltas = {
        name: float(reranked[name]) - float(hybrid[name])
        for name in (
            "recall_at_1",
            "recall_at_3",
            "mrr",
            "metadata_hit_rate_at_3",
            "reference_precision_at_3",
        )
    }
    return {"hybrid": hybrid, "reranked": reranked, "delta": deltas}
