"""
基础通用函数
"""
import re

from ..schemas.job_schema import GitLabJobContext


def _normalize_llm_output(
        parsed: dict,
        references_override: list[dict] | None = None,
) -> dict:
    """llm structure output 内容优化"""
    suggestions = parsed.get("suggestions")
    if isinstance(suggestions, list):
        parsed["suggestions"] = [
            str(item).strip()
            for item in suggestions
            if str(item).strip()
        ][:5]

    if references_override is not None:
        parsed["references"] = references_override

    return parsed


def _format_docs(docs: list[dict] | None) -> str:
    """解析知识数据结构"""
    if not docs:
        return "[]"
    return "\n\n".join(
        f"[{doc.get('title', '')}] {doc.get('content', '')}"
        for doc in docs
    )


def build_enriched_log(trace: str, context: GitLabJobContext) -> str:
    """格式化构造优化输出日志"""
    return f"""
    CI Context:
    project_id: {context.project_id}
    pipeline_id: {context.pipeline_id}
    job_id: {context.job_id}
    job_name: {context.job_name}
    stage: {context.stage}
    status: {context.status}
    branch: {context.branch}
    commit_sha: {context.commit_sha}
    failure_reason: {context.failure_reason}
    duration: {context.duration}

    CI Trace:
    {trace}
    """.strip()


def truncate_trace(trace: str, max_lines: int = 200) -> str:
    """trace日志数据最大chunk获取拼接"""
    lines = trace.splitlines()
    return "\n".join(lines[-max_lines:])


def extract_relevant_lines(trace: str, context_window: int = 3) -> str:
    """
    解析提取trace内容
    :param trace:
    :param context_window:
    :return:
    """
    ERROR_KEYWORDS = [
        "error",
        "failed",
        "exception",
        "traceback",
        "modulenotfounderror",
        "syntaxerror",
        "assertionerror",
        "keyerror",
        "timeout",
        "forbidden",
        "unauthorized",
    ]
    lines = trace.splitlines()
    matched_indices = []

    for i, line in enumerate(lines):
        lower = line.lower()
        if any(keyword in lower for keyword in ERROR_KEYWORDS):
            matched_indices.append(i)

    selected = set()
    for idx in matched_indices:
        start = max(0, idx - context_window)
        end = min(len(lines), idx + context_window + 1)
        selected.update(range(start, end))

    if not selected:
        return truncate_trace(trace)

    return "\n".join(lines[i] for i in sorted(selected))


def mask_sensitive_info(text: str) -> str:
    """
    信息脱敏
    :param text:
    :return:
    """
    patterns = [
        r"(?i)(token=)[^\s]+",
        r"(?i)(password=)[^\s]+",
        r"(?i)(secret=)[^\s]+",
        r"(?i)(api_key=)[^\s]+",
    ]

    masked = text
    for pattern in patterns:
        masked = re.sub(pattern, r"\1******", masked)

    return masked
