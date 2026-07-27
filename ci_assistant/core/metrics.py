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

