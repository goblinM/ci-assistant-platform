from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Reference(BaseModel):
    id: str
    title: str
    source: str
    content: str
    score: float | None = None


class DiagnosisResult(BaseModel):
    error_type: str
    summary: str
    reason: str
    suggestions: list[str] = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    references: list[Reference] = Field(default_factory=list)
    fallback_used: bool = False

