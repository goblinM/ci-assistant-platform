from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DiagnosisFeedbackRequest(BaseModel):
    """定义诊断评分、建议采纳、纠正类型和脱敏评论的写入边界。"""

    rating: Literal["helpful", "partially_helpful", "not_helpful"]
    accepted_suggestion: bool | None = None
    corrected_error_type: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class DiagnosisFeedbackView(BaseModel):
    """表示单条诊断反馈及其创建、更新时间的 API 查询视图。"""

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
    """表示租户反馈评分分布和建议采纳率的聚合视图。"""

    total: int
    ratings: dict[str, int]
    accepted_suggestions: int
    acceptance_total: int
    acceptance_rate: float | None
