import json
from pathlib import Path

from ci_assistant.evaluation.agent import evaluate_agent_comparison


def test_agent_p0_dataset_has_ten_evidence_cases() -> None:
    """验证 P0 固定用例覆盖三类 Provider 和至少十个补充证据场景。"""
    cases = json.loads(
        (Path(__file__).parents[1] / "agent_evaluation_cases.json").read_text()
    )
    assert len(cases) >= 10
    assert {case["provider"] for case in cases} == {"gitlab", "jenkins", "github"}
    assert all(case["expected_tools"] for case in cases)


def test_agent_comparison_reports_quality_safety_and_cost_metrics() -> None:
    """验证对照评测同时输出结果质量、工具安全、效率和成本指标。"""
    case = {
        "expected_error_type": "test_failed",
        "expected_tools": ["get_job_log"],
        "workflow": {"task_success": False, "error_type": "unknown"},
        "agent": {
            "task_success": True,
            "error_type": "test_failed",
            "tool_calls": ["get_job_log"],
            "rounds": 2,
            "latency_ms": 20,
            "input_tokens": 100,
            "output_tokens": 25,
            "cost": 0.01,
        },
    }
    metrics = evaluate_agent_comparison([case])
    assert metrics["agent_task_success_rate"] == 1
    assert metrics["tool_precision"] == 1
    assert metrics["tool_recall"] == 1
    assert metrics["average_rounds"] == 2
    assert metrics["average_cost"] == 0.01
    assert metrics["average_output_tokens"] == 25
    assert metrics["p95_latency_ms"] == 20
