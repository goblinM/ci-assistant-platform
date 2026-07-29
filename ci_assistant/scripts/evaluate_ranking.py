from __future__ import annotations

import argparse
import json
from pathlib import Path

from ci_assistant.evaluation.ranking import compare_rankings


def main() -> None:
    """读取固定排序用例并输出 Hybrid/Reranker 指标对比 JSON。"""
    parser = argparse.ArgumentParser(description="Evaluate offline RAG ranking")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parents[1] / "ranking_evaluation_cases.json",
    )
    arguments = parser.parse_args()
    cases = json.loads(arguments.dataset.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("ranking evaluation dataset must be a list")
    print(json.dumps(compare_rankings(cases), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
