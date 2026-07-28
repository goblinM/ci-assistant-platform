from __future__ import annotations

import re
from typing import Any

import numpy as np

from .index import FaissIndexStore


class HybridRetriever:
    def __init__(self, store: FaissIndexStore) -> None:
        self.store = store

    def retrieve(
        self,
        *,
        query_vector: np.ndarray,
        query_text: str,
        tenant_id: str,
        project_id: str | None,
        provider: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """按查询条件检索知识数据。"""
        candidates = self.store.search(
            query_vector,
            tenant_id=tenant_id,
            project_id=project_id,
            provider=provider,
            top_k=max(top_k * 4, top_k),
        )
        query_terms = set(re.findall(r"[\w.-]+", query_text.lower()))
        for candidate in candidates:
            content_terms = set(
                re.findall(r"[\w.-]+", candidate.get("content", "").lower())
            )
            keyword_score = (
                len(query_terms & content_terms) / len(query_terms) if query_terms else 0
            )
            metadata_score = 0.0
            if provider and candidate.get("provider") == provider:
                metadata_score += 0.1
            if project_id and candidate.get("project_id") == project_id:
                metadata_score += 0.1
            candidate["semantic_score"] = candidate["score"]
            candidate["keyword_score"] = keyword_score
            candidate["metadata_score"] = metadata_score
            candidate["score"] = (
                candidate["semantic_score"] * 0.65
                + keyword_score * 0.25
                + metadata_score
            )
        return sorted(candidates, key=lambda item: item["score"], reverse=True)[:top_k]

