from prometheus_client import Counter, Histogram


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
