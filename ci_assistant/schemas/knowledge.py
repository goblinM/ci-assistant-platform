from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateKnowledgeDocument(BaseModel):
    tenant_id: UUID
    project_id: UUID | None = None
    provider: Literal["gitlab", "jenkins"] | None = None
    title: str = Field(min_length=1, max_length=500)
    format: Literal["markdown", "json"]
    content: str = Field(min_length=1, max_length=5_000_000)
    source_type: str = Field(default="customer", max_length=50)
    source_url: str | None = Field(default=None, max_length=1000)
    license: str | None = Field(default=None, max_length=100)


class KnowledgeDocumentView(BaseModel):
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

