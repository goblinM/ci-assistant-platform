from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateKnowledgeDocument(BaseModel):
    """定义带租户作用域、来源信息和大小限制的文本知识负载。"""

    tenant_id: UUID
    project_id: UUID | None = None
    provider: Literal["gitlab", "jenkins", "github"] | None = None
    title: str = Field(min_length=1, max_length=500)
    format: Literal["markdown", "json"]
    content: str = Field(min_length=1, max_length=5_000_000)
    source_type: str = Field(default="customer", max_length=50)
    source_url: str | None = Field(default=None, max_length=1000)
    license: str | None = Field(default=None, max_length=100)


class CreateParsedKnowledgeDocument(CreateKnowledgeDocument):
    """表示 PDF、DOCX 或 HTML 解析完成后的内部知识文档负载。"""

    format: Literal["pdf", "docx", "html"]


class KnowledgeDocumentView(BaseModel):
    """表示可对外查询的知识文档元数据，不暴露完整正文。"""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    project_id: UUID | None
    provider: str | None
    title: str
    format: str
    content_hash: str
    version: int
    status: str
