"""
工具注册入口。

CI_TOOLS_SCHEMA 是工具元信息的单一事实源；这里负责把 schema 中声明的工具
映射到真实函数并注册到 ToolsExecutor。
"""
from collections.abc import Callable
from typing import Any

from ci_analysis_demo.tools.base import ToolSpec
from ci_analysis_demo.tools.ci_tools import (
    check_dependency_file,
    query_failure_history,
    query_job_context,
    query_pipeline_context,
    query_recent_commits,
    trim_tool_result,
)
from ci_analysis_demo.tools.executor import ToolsExecutor
from ci_analysis_demo.tools.schemas import CI_TOOLS_SCHEMA


# TOOL_FUNCTIONS 加映射
TOOL_FUNCTIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "query_failure_history": query_failure_history,
    "query_pipeline_context": query_pipeline_context,
    "query_job_context": query_job_context,
    "check_dependency_file": check_dependency_file,
    "query_recent_commits": query_recent_commits,
}


def create_default_tools_executor(gitlab_client=None) -> ToolsExecutor:
    executor = ToolsExecutor(gitlab_client=gitlab_client)

    for tool_schema in CI_TOOLS_SCHEMA:
        if not tool_schema.get("enabled", True):
            continue

        func_name = tool_schema.get("func_name", tool_schema["name"])
        func = TOOL_FUNCTIONS.get(func_name)
        if func is None:
            raise ValueError(f"Tool function not found: {func_name}")

        executor.register(
            ToolSpec(
                name=tool_schema["name"],
                description=tool_schema["description"],
                func=func,
                parameters_schema=tool_schema["parameters"],
                provider=tool_schema.get("provider", "local"),
                enabled=tool_schema.get("enabled", True),
                read_only=tool_schema.get("read_only", True),
                tags=tool_schema.get("tags", []),
                result_trimmer=trim_tool_result,
                trigger_keywords=tool_schema.get("trigger_keywords", []),
                always_candidate=tool_schema.get("always_candidate", False),
            )
        )

    return executor
