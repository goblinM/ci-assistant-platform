from enum import Enum
from typing import Annotated, Literal, List

from pydantic import BaseModel, Field

ErrorType = Literal[
    "dependency_missing",
    "syntax_error",
    "test_failed",
    "timeout",
    "permission_error",
    "env_config_error",
    "repo_auth_failed",
    "docker_build_failed",
    "image_pull_failed",
    "network_error",
    "resource_exhausted",
    "dependency_conflict",
    "unknown",
]

Confidence = Literal["high", "medium", "low"]
SuggestionList = Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1, max_length=5)]


class ToolMode(str, Enum):
    """
    tool_mode = none
    日志 + RAG + LLM

    tool_mode = rule
    日志 + RAG + 规则触发工具 + LLM

    tool_mode = llm
    日志 + RAG + LLM 自主选择工具 + ToolsExecutor + LLM
    """
    none = "none"
    rule = "rule"
    llm = "llm"


class ReferenceItem(BaseModel):
    """表示兼容诊断响应中由真实检索文档转换得到的引用。"""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    category: str
    tags: List[str]


class AnalysisLogRequest(BaseModel):
    """定义旧日志分析接口的日志、CI 上下文和分析模式输入。"""

    log_text: str = Field(min_length=1)
    project_name: str | None = None
    pipeline_id: str | None = None
    job_name: str | None = None
    use_rag: bool = True
    use_tools: bool = True
    request_id: str | None = None
    tool_mode: ToolMode = ToolMode.rule


class AnalysisLogResponse(BaseModel):
    """定义旧日志分析接口保持兼容的结构化诊断与引用响应。"""

    error_type: ErrorType
    summary: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    suggestions: SuggestionList
    confidence: Confidence
    references: List[ReferenceItem] | None = None

    trace_id: str | None = None
    fallback_used: bool = False
    extra: dict | None = None
