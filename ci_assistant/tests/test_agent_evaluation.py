import json
import asyncio
from types import SimpleNamespace
from pathlib import Path

from ci_assistant.evaluation.agent import (
    evaluate_agent_comparison,
    orchestration_output_to_evaluation,
    run_agent_ab_evaluation,
)
from ci_assistant.schemas.result import DiagnosisResult


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


def test_agent_ab_harness_executes_both_paths_for_each_case() -> None:
    """验证 A/B Harness 实际调用两个运行器，而不是只消费预填统计结果。"""
    calls: list[tuple[str, str]] = []
    cases = [{"id": "case-1", "expected_error_type": "test_failed", "expected_tools": []}]

    async def workflow(case):
        """模拟真实异步 Workflow 入口。"""
        calls.append(("workflow", case["id"]))
        return {"task_success": True, "error_type": "test_failed"}

    def agent(case):
        """模拟真实同步 Agent 入口。"""
        calls.append(("agent", case["id"]))
        return {"task_success": True, "error_type": "test_failed", "rounds": 1}

    report = asyncio.run(
        run_agent_ab_evaluation(cases, workflow_runner=workflow, agent_runner=agent)
    )
    assert calls == [("workflow", "case-1"), ("agent", "case-1")]
    assert report["metrics"]["case_count"] == 1
    assert report["cases"][0]["agent"]["latency_ms"] >= 0


def test_orchestration_adapter_extracts_agent_quality_and_safety_fields() -> None:
    """验证现有编排结果可直接转换为不含日志正文的 A/B 评测记录。"""
    result = DiagnosisResult(
        error_type="test_failed",
        summary="Tests failed",
        reason="Assertion failed",
        suggestions=["Inspect assertion"],
        confidence="high",
    )
    output = SimpleNamespace(
        result=result,
        trace={
            "duration_ms": 12.5,
            "fallback_used": False,
            "agent": {
                "rounds": 2,
                "model_input_tokens": 100,
                "model_output_tokens": 20,
                "steps": [
                    {"action": "tool_request", "tool_name": "get_job_log"},
                    {"action": "self_check", "error_code": "SELF_CHECK_LOW_CONFIDENCE"},
                ],
            },
        },
    )
    record = orchestration_output_to_evaluation(output)
    assert record["tool_calls"] == ["get_job_log"]
    assert record["self_checks"] == 1
    assert record["input_tokens"] == 100
    assert record["latency_ms"] == 12.5
