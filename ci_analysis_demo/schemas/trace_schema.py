from typing import Any

from pydantic import BaseModel, Field


class AnalysisTrace(BaseModel):
    """记录旧分析链路的 RAG、工具、模型、校验和降级追踪字段。"""

    trace_id: str
    project_name: str | None = None
    pipeline_id: str | None = None
    job_name: str | None = None

    log_length: int = 0

    rag_enabled: bool = False
    rag_query: str | None = None
    rag_filters: dict[str, Any] = Field(default_factory=dict)
    rag_top_k: int = 0
    rag_candidate_count: int = 0
    rag_hit_doc_ids: list[str] = Field(default_factory=list)
    rag_hit_titles: list[str] = Field(default_factory=list)
    rag_scores: list[float | None] = Field(default_factory=list)
    rag_duration_ms: float | None = None
    rag_context_length: int = 0

    tools_enabled: bool = False
    tool_names: list[str] = Field(default_factory=list)
    tool_duration_ms: float | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    successful_tools: list[str] = Field(default_factory=list)
    failed_tools: list[str] = Field(default_factory=list)

    prompt_length: int = 0
    llm_model: str | None = None
    tool_selection_duration_ms: float | None = None
    final_prompt_length: int = 0
    llm_duration_ms: float | None = None
    llm_success: bool = False

    schema_valid: bool = False
    error_type: str | None = None
    confidence: str | None = None

    total_duration_ms: float | None = None
    fallback_used: bool = False
    error_message: str | None = None

    extra: dict[str, Any] = Field(default_factory=dict)
