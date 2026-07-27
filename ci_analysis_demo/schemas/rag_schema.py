"""RAG 检索输入输出结构。"""
from typing import Any

from pydantic import BaseModel, Field


class RAGDocument(BaseModel):
    doc_id: str
    title: str
    source: str
    content: str
    score: float | None = None
    semantic_score: float | None = None
    keyword_score: float = 0.0
    metadata_score: float = 0.0
    retrieval_sources: list[str] = Field(default_factory=list)
    error_type: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    def to_reference(self) -> dict[str, Any]:
        """转换成 AnalysisLogResponse.references 所需结构。"""
        return {
            "id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "content": self.content,
            "category": self.category or "",
            "tags": self.tags,
        }


class RAGResult(BaseModel):
    query: str
    filters: dict = Field(default_factory=dict)
    top_k: int
    documents: list[RAGDocument] = Field(default_factory=list)
    candidate_count: int = 0
    duration_ms: float | None = None

    @property
    def hit_titles(self) -> list[str]:
        return [doc.title for doc in self.documents]

    @property
    def hit_doc_ids(self) -> list[str]:
        return [doc.doc_id for doc in self.documents]

    @property
    def scores(self) -> list[float | None]:
        return [doc.score for doc in self.documents]

    def to_references(self) -> list[dict[str, Any]]:
        return [doc.to_reference() for doc in self.documents]

    def to_prompt_context(self, max_chars: int | None = None) -> str:
        """按字符预算拼接上下文，至少保留已命中文档的标题和来源。"""
        if not self.documents:
            return "[]"

        chunks: list[str] = []
        remaining = max_chars

        for index, doc in enumerate(self.documents, start=1):
            prefix = f"""[参考资料 {index}]
doc_id: {doc.doc_id}
title: {doc.title}
source: {doc.source}
error_type: {doc.error_type}
content:
"""
            content = doc.content
            suffix = "\n"

            if remaining is not None:
                separator_length = 2 if chunks else 0
                available = remaining - len(prefix) - len(suffix) - separator_length
                if available <= 0:
                    break
                if len(content) > available:
                    marker = "\n...[内容已按 RAG context budget 截断]"
                    if available <= len(marker):
                        content = marker[:available]
                    else:
                        content = content[:available - len(marker)] + marker

            chunk = f"{prefix}{content}{suffix}"
            chunks.append(chunk)
            if remaining is not None:
                remaining -= len(chunk) + (2 if len(chunks) > 1 else 0)
                if remaining <= 0:
                    break

        return "\n\n".join(chunks)
