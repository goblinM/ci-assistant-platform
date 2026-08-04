from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Reference(BaseModel):
    """表示由检索层提供并可追溯到真实知识来源的引用。"""

    id: str
    title: str
    source: str
    content: str
    score: float | None = None


class DiagnosisResult(BaseModel):
    """定义模型或规则网关必须满足的结构化诊断输出。"""

    error_type: str
    summary: str
    reason: str
    suggestions: list[str] = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    references: list[Reference] = Field(default_factory=list)
    fallback_used: bool = False
