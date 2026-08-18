from __future__ import annotations

from typing import Any


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
    }
