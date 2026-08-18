from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateLogDiagnosisRequest(BaseModel):
    """定义租户直接提交日志创建异步诊断的请求边界。"""

    tenant_id: UUID
    project_id: UUID | None = None
    log_text: str = Field(min_length=1, max_length=1_000_000)
    use_rag: bool = True
    use_tools: bool = True
    mode: Literal["workflow", "agent"] = "workflow"


class CreateRunDiagnosisRequest(BaseModel):
    """定义通过 CI 连接和运行标识创建异步诊断的请求边界。"""

    connection_id: str = Field(min_length=1, max_length=100)
    project_ref: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    project_id: UUID | None = None
    use_rag: bool = True
    use_tools: bool = True
    mode: Literal["workflow", "agent"] = "workflow"


class DiagnosisAccepted(BaseModel):
    """表示诊断请求已持久化并成功进入异步处理队列。"""

    diagnosis_id: UUID
    trace_id: str
    status: Literal["queued"]


class DiagnosisView(BaseModel):
    """表示诊断生命周期、结构化结果和稳定错误码的查询视图。"""

    model_config = {"from_attributes": True}

    id: UUID
    trace_id: str
    status: str
    source: str
    result: dict[str, Any] | None
    error_code: str | None
