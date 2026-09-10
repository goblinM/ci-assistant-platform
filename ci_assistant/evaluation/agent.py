from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any


EvaluationRunner = Callable[
    [dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]
]


def orchestration_output_to_evaluation(output: Any) -> dict[str, Any]:
    """把现有编排输出转换为 A/B Harness 的稳定、无日志评测记录。"""
    trace = dict(output.trace or {})
    agent = dict(trace.get("agent") or {})
    steps = list(agent.get("steps") or [])
    error_codes = [str(step.get("error_code") or "") for step in steps]
    return {
        "task_success": output.result.error_type != "unknown",
        "error_type": output.result.error_type,
        "tool_calls": [
            step.get("tool_name")
            for step in steps
            if step.get("action") == "tool_request" and step.get("tool_name")
        ],
        "invalid_tool_calls": sum(
            code in {"MODEL_DECISION_INVALID", "EMPTY_OBSERVATION"}
            for code in error_codes
        ),
        "repeated_tool_calls": error_codes.count("REPEATED_TOOL_CALL"),
        "policy_denied_calls": error_codes.count("TOOL_POLICY_DENIED"),
        "self_checks": sum(step.get("action") == "self_check" for step in steps),
        "rounds": int(agent.get("rounds") or 0),
        "latency_ms": float(trace.get("duration_ms") or 0),
        "input_tokens": int(
            agent.get("model_input_tokens")
            or agent.get("estimated_input_tokens")
            or 0
        ),
        "output_tokens": int(agent.get("model_output_tokens") or 0),
        "fallback_used": bool(trace.get("fallback_used")),
    }


async def run_agent_ab_evaluation(
    cases: list[dict[str, Any]],
    *,
    workflow_runner: EvaluationRunner,
    agent_runner: EvaluationRunner,
) -> dict[str, Any]:
    """真实执行每个固定用例的 Workflow/Agent Runner，并汇总统一对照指标。"""
    executed: list[dict[str, Any]] = []
    for source in cases:
        case = dict(source)
        case["workflow"] = await _run_case(workflow_runner, case)
        case["agent"] = await _run_case(agent_runner, case)
        executed.append(case)
    return {"metrics": evaluate_agent_comparison(executed), "cases": executed}


async def _run_case(
    runner: EvaluationRunner,
    case: dict[str, Any],
) -> dict[str, Any]:
    """执行同步或异步 Runner，并在其未提供时补充真实墙钟延迟。"""
    started = time.perf_counter()
    outcome = runner(case)
    if inspect.isawaitable(outcome):
        outcome = await outcome
    result = dict(outcome)
    result.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 2))
    return result


def evaluate_agent_comparison(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """比较固定用例中 Workflow 与 Agent 的结果、工具、安全、轮次和成本指标。"""
    if not cases:
        raise ValueError("agent evaluation requires at least one case")
    totals: dict[str, float] = {
        "workflow_task_success": 0,
        "agent_task_success": 0,
        "workflow_error_type_accuracy": 0,
        "agent_error_type_accuracy": 0,
        "tool_true_positive": 0,
        "tool_selected": 0,
        "tool_expected": 0,
        "invalid_tool_calls": 0,
        "repeated_tool_calls": 0,
        "policy_denied_calls": 0,
        "agent_rounds": 0,
        "agent_latency_ms": 0,
        "agent_input_tokens": 0,
        "agent_output_tokens": 0,
        "agent_cost": 0,
        "agent_fallbacks": 0,
        "agent_self_checks": 0,
    }
    latencies: list[float] = []
    for case in cases:
        expected_type = case["expected_error_type"]
        workflow = case["workflow"]
        agent = case["agent"]
        expected_tools = set(case.get("expected_tools") or [])
        selected_tools = set(agent.get("tool_calls") or [])
        latencies.append(float(agent.get("latency_ms", 0)))
        totals["workflow_task_success"] += float(bool(workflow.get("task_success")))
        totals["agent_task_success"] += float(bool(agent.get("task_success")))
        totals["workflow_error_type_accuracy"] += float(
            workflow.get("error_type") == expected_type
        )
        totals["agent_error_type_accuracy"] += float(agent.get("error_type") == expected_type)
        totals["tool_true_positive"] += len(expected_tools & selected_tools)
        totals["tool_selected"] += len(selected_tools)
        totals["tool_expected"] += len(expected_tools)
        for name in (
            "invalid_tool_calls",
            "repeated_tool_calls",
            "policy_denied_calls",
            "rounds",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "cost",
            "self_checks",
        ):
            metric_name = (
                f"agent_{name}"
                if name
                in {
                    "rounds",
                    "latency_ms",
                    "input_tokens",
                    "output_tokens",
                    "cost",
                    "self_checks",
                }
                else name
            )
            totals[metric_name] += float(agent.get(name, 0))
        totals["agent_fallbacks"] += float(bool(agent.get("fallback_used")))

    count = len(cases)
    tool_precision = (
        totals["tool_true_positive"] / totals["tool_selected"]
        if totals["tool_selected"]
        else 1.0
    )
    tool_recall = (
        totals["tool_true_positive"] / totals["tool_expected"]
        if totals["tool_expected"]
        else 1.0
    )
    return {
        "case_count": count,
        "workflow_task_success_rate": totals["workflow_task_success"] / count,
        "agent_task_success_rate": totals["agent_task_success"] / count,
        "workflow_error_type_accuracy": totals["workflow_error_type_accuracy"] / count,
        "agent_error_type_accuracy": totals["agent_error_type_accuracy"] / count,
        "tool_precision": tool_precision,
        "tool_recall": tool_recall,
        "invalid_tool_call_rate": totals["invalid_tool_calls"] / count,
        "repeated_tool_call_rate": totals["repeated_tool_calls"] / count,
        "policy_denied_call_rate": totals["policy_denied_calls"] / count,
        "average_rounds": totals["agent_rounds"] / count,
        "average_latency_ms": totals["agent_latency_ms"] / count,
        "p95_latency_ms": sorted(latencies)[max(0, (95 * count + 99) // 100 - 1)],
        "average_input_tokens": totals["agent_input_tokens"] / count,
        "average_output_tokens": totals["agent_output_tokens"] / count,
        "average_cost": totals["agent_cost"] / count,
        "fallback_rate": totals["agent_fallbacks"] / count,
        "average_self_checks": totals["agent_self_checks"] / count,
    }
