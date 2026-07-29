from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DiagnosisFeedbackRequest(BaseModel):
    """创建或更新诊断反馈的请求。"""

    rating: Literal["helpful", "partially_helpful", "not_helpful"]
    accepted_suggestion: bool | None = None
    corrected_error_type: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class DiagnosisFeedbackView(BaseModel):
    """诊断反馈响应。"""

    model_config = {"from_attributes": True}

    id: UUID
    diagnosis_id: UUID
    rating: str
    accepted_suggestion: bool | None
    corrected_error_type: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackSummaryView(BaseModel):
    """租户反馈汇总响应。"""

    total: int
    ratings: dict[str, int]
    accepted_suggestions: int
    acceptance_total: int
    acceptance_rate: float | None
