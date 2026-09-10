from collections.abc import Iterable

from prometheus_client import Counter, Histogram

from ci_assistant.schemas.agent import AgentStep


HTTP_REQUESTS = Counter(
    "ci_assistant_http_requests_total",
    "HTTP requests handled by the API.",
    ["method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "ci_assistant_http_request_duration_seconds",
    "HTTP request duration.",
    ["method", "path"],
)
DIAGNOSIS_TASKS = Counter(
    "ci_assistant_diagnosis_tasks_total",
    "Diagnosis tasks by terminal status.",
    ["status"],
)
AGENT_RUNS = Counter(
    "ci_assistant_agent_runs_total",
    "Experimental Agent runs by stable stop reason.",
    ["stop_reason"],
)
AGENT_ROUNDS = Histogram(
    "ci_assistant_agent_rounds",
    "Rounds consumed by an experimental Agent run.",
    buckets=(1, 2, 3, 4, 5, 8),
)
AGENT_TOOL_CALLS = Histogram(
    "ci_assistant_agent_tool_calls",
    "Read-only tool calls consumed by an experimental Agent run.",
    buckets=(0, 1, 2, 3, 4, 8, 16),
)
AGENT_INPUT_TOKENS = Histogram(
    "ci_assistant_agent_estimated_input_tokens",
    "Estimated input tokens consumed by an experimental Agent run.",
    buckets=(500, 1_000, 2_000, 4_000, 7_500, 15_000, 30_000),
)
AGENT_TOOL_DECISIONS = Counter(
    "ci_assistant_agent_tool_decisions_total",
    "Agent read-only tool decisions by bounded tool name and outcome.",
    ["tool", "outcome"],
)
AGENT_SELF_CHECKS = Counter(
    "ci_assistant_agent_self_checks_total",
    "Agent bounded self-checks by trigger.",
    ["trigger"],
)
AGENT_EVIDENCE_GAPS = Counter(
    "ci_assistant_agent_evidence_gaps_total",
    "Agent tool requests that declared an evidence gap.",
    ["tool"],
)

_METRIC_TOOL_NAMES = {
    "get_run_context",
    "get_job_context",
    "get_job_log",
    "get_changes",
}


def observe_agent_steps(steps: Iterable[AgentStep]) -> None:
    """把脱敏 Agent Step 记录为低基数工具、自检和证据缺口指标。"""
    for step in steps:
        if step.action == "self_check":
            trigger = (
                "low_confidence"
                if step.error_code == "SELF_CHECK_LOW_CONFIDENCE"
                else "evidence_conflict"
            )
            AGENT_SELF_CHECKS.labels(trigger=trigger).inc()
            continue
        if step.action != "tool_request":
            continue
        tool = step.tool_name if step.tool_name in _METRIC_TOOL_NAMES else "unknown"
        if step.evidence_gap:
            AGENT_EVIDENCE_GAPS.labels(tool=tool).inc()
        outcomes = {
            "TOOL_POLICY_DENIED": "policy_denied",
            "REPEATED_TOOL_CALL": "repeated",
            "EMPTY_OBSERVATION": "empty",
            "TOOL_EXECUTION_FAILED": "execution_failed",
        }
        outcome = outcomes.get(step.error_code or "", "executed")
        AGENT_TOOL_DECISIONS.labels(tool=tool, outcome=outcome).inc()
