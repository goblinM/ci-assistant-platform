from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateLogDiagnosisRequest(BaseModel):
    tenant_id: UUID
    project_id: UUID | None = None
    log_text: str = Field(min_length=1, max_length=1_000_000)
    use_rag: bool = True
    use_tools: bool = True


class CreateRunDiagnosisRequest(BaseModel):
    connection_id: str = Field(min_length=1, max_length=100)
    project_ref: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    project_id: UUID | None = None
    use_rag: bool = True
    use_tools: bool = True


class DiagnosisAccepted(BaseModel):
    diagnosis_id: UUID
    trace_id: str
    status: Literal["queued"]


class DiagnosisView(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    trace_id: str
    status: str
    source: str
    result: dict[str, Any] | None
    error_code: str | None
