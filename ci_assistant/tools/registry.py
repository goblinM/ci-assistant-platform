from ci_assistant.domain.ci import ProviderCapability
from ci_assistant.domain.tools import ToolSpec

from .builtins import get_changes, get_job_context, get_job_log, get_run_context


def default_tool_specs() -> list[ToolSpec]:
    """构建平台默认只读 Tool 规格及其 Provider 能力和触发条件。"""
    return [
        ToolSpec(
            name="get_run_context",
            description="Read normalized run and job context.",
            func=get_run_context,
            capability=ProviderCapability.RUN_READ,
            input_schema=_identifier_schema("run_id"),
            tags=frozenset({"ci", "run"}),
            trigger_keywords=frozenset({"pipeline", "build", "run"}),
        ),
        ToolSpec(
            name="get_job_context",
            description="Read normalized job context.",
            func=get_job_context,
            capability=ProviderCapability.JOB_READ,
            input_schema=_identifier_schema("job_id"),
            tags=frozenset({"ci", "job"}),
            trigger_keywords=frozenset({"job", "stage", "runner", "agent"}),
        ),
        ToolSpec(
            name="get_job_log",
            description="Read a bounded CI job log.",
            func=get_job_log,
            capability=ProviderCapability.LOG_READ,
            input_schema=_identifier_schema("job_id"),
            tags=frozenset({"ci", "log"}),
            trigger_keywords=frozenset({"error", "failed", "exception"}),
        ),
        ToolSpec(
            name="get_changes",
            description="Read recent changes associated with a run.",
            func=get_changes,
            capability=ProviderCapability.CHANGES_READ,
            input_schema=_identifier_schema("run_id"),
            tags=frozenset({"ci", "changes"}),
            trigger_keywords=frozenset({"commit", "change", "regression"}),
        ),
    ]


def _identifier_schema(identifier: str) -> dict[str, object]:
    """构造由服务端注入项目标识和运行标识的只读工具参数 Schema。"""
    return {
        "type": "object",
        "properties": {
            "project_ref": {"type": "string", "minLength": 1},
            identifier: {"type": "string", "minLength": 1},
        },
        "required": ["project_ref", identifier],
        "additionalProperties": False,
    }
