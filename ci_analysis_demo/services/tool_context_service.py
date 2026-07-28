"""
负责收集工具上下文
"""
from ..tools.base import ToolContext, ToolRuntimeContext
from ..tools.executor import ToolsExecutor
from ..tools.rules import extract_primary_error_keyword, extract_error_keywords


def build_tool_calls(log_text: str,
                     tools_executor: ToolsExecutor,
                     project_name: str | None = None,
                     pipeline_id: str | None = None,
                     job_name: str | None = None,
                     primary_error: dict | None = None) -> list[dict]:
    # 构造tool calls request
    """创建 ``build_tool_calls`` 对应的领域对象或结果。"""
    primary_error = primary_error or extract_primary_error_keyword(log_text)
    project_id = project_name
    calls: list[dict] = []
    selected_tools = set(
        tools_executor.select_tool_names(
            tags=_select_tool_tags(primary_error, project_id, pipeline_id, job_name),
            text=log_text,
            trigger_keywords=_select_tool_trigger_keywords(primary_error, pipeline_id, job_name),
        )
    )
    # 工具 1：历史失败查询
    if primary_error and "query_failure_history" in selected_tools:
        calls.append(
            {
                "tool_name": "query_failure_history",
                "arguments": {
                    "project_name": project_name,
                    "error_keyword": primary_error["keyword"],
                    "error_type": primary_error["error_type"],
                },
            }
        )

    # 工具 2：Pipeline 上下文查询
    if (pipeline_id or job_name) and "query_pipeline_context" in selected_tools:
        calls.append(
            {
                "tool_name": "query_pipeline_context",
                "arguments": {
                    "project_id": project_id,
                    "pipeline_id": pipeline_id,
                    "job_name": job_name,
                },
            }
        )

    if (
            primary_error
            and primary_error["error_type"] == "dependency_missing"
            and "check_dependency_file" in selected_tools
    ):
        groups = primary_error.get("groups") or []
        package_name = groups[0] if groups else None
        if package_name:
            calls.append(
                {
                    "tool_name": "check_dependency_file",
                    "arguments": {
                        "project_id": project_id,
                        "package_name": package_name,
                    },
                }
            )

    if project_id and "query_recent_commits" in selected_tools:
        calls.append(
            {
                "tool_name": "query_recent_commits",
                "arguments": {
                    "project_id": project_id,
                    "limit": 5,
                },
            }
        )

    return calls


def _select_tool_tags(
        primary_error: dict | None,
        project_id: str | None,
        pipeline_id: str | None,
        job_name: str | None,
) -> list[str]:
    tags = ["diagnosis"]
    if project_id:
        tags.extend(["gitlab", "repository"])
    if pipeline_id or job_name:
        tags.extend(["pipeline", "job", "context"])
    if primary_error and primary_error.get("error_type") == "dependency_missing":
        tags.append("dependency")
    return tags


def _select_tool_trigger_keywords(
        primary_error: dict | None,
        pipeline_id: str | None,
        job_name: str | None,
) -> list[str]:
    """把规则识别出的结构化错误转换成工具选择关键词。"""
    keywords: list[str] = []

    if primary_error:
        for field in ("keyword", "matched_text", "error_type", "description"):
            value = primary_error.get(field)
            if value:
                keywords.append(str(value))

        keywords.extend(str(group) for group in primary_error.get("groups") or [] if group)

    if pipeline_id:
        keywords.extend(["pipeline", str(pipeline_id)])

    if job_name:
        keywords.extend(["job", job_name])

    return keywords


async def collect_tool_context(
        log_text: str,
        tools_executor: ToolsExecutor,
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        primary_error: dict | None = None,
        runtime_context: ToolRuntimeContext | None = None,
) -> ToolContext:
    """收集工具上下文"""
    matched_errors = extract_error_keywords(log_text)
    primary_error = primary_error or (matched_errors[0] if matched_errors else None)
    calls = build_tool_calls(log_text=log_text,
                             tools_executor=tools_executor,
                             project_name=project_name,
                             pipeline_id=pipeline_id,
                             job_name=job_name,
                             primary_error=primary_error,
                             )
    results = await tools_executor.execute_many(
        calls=calls,
        runtime_context=runtime_context,
    )
    return ToolContext(
        primary_error=primary_error,
        matched_errors=matched_errors,
        results=results,
    )
