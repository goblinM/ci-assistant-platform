from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class IndexedChunk:
    vector_id: int
    content: str
    tenant_id: str
    project_id: str | None
    provider: str | None
    metadata: dict[str, Any]


class FaissIndexStore:
    """Versioned FAISS index with atomic CURRENT pointer switching."""

    def __init__(self, root: Path, dimension: int) -> None:
        self.root = root
        self.dimension = dimension

    def publish(
        self,
        *,
        version: str,
        vectors: np.ndarray,
        chunks: list[IndexedChunk],
    ) -> None:
        """执行 ``publish`` 对应的知识库处理流程。"""
        import faiss

        if vectors.shape != (len(chunks), self.dimension):
            raise ValueError("vector matrix shape does not match chunks and dimension")
        self.root.mkdir(parents=True, exist_ok=True)
        version_dir = self.root / version
        if version_dir.exists():
            raise ValueError(f"index version already exists: {version}")
        temporary = self.root / f".{version}.tmp"
        temporary.mkdir()

        matrix = np.asarray(vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.dimension))
        ids = np.asarray([chunk.vector_id for chunk in chunks], dtype="int64")
        index.add_with_ids(matrix, ids)
        faiss.write_index(index, str(temporary / "index.faiss"))
        (temporary / "metadata.json").write_text(
            json.dumps(
                {str(chunk.vector_id): chunk.__dict__ for chunk in chunks},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, version_dir)
        pointer = self.root / ".CURRENT.tmp"
        pointer.write_text(version, encoding="utf-8")
        os.replace(pointer, self.root / "CURRENT")

    def current_version(self) -> str | None:
        """获取 ``current_version`` 对应的数据。"""
        pointer = self.root / "CURRENT"
        return pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None

    def search(
        self,
        query_vector: np.ndarray,
        *,
        tenant_id: str,
        project_id: str | None,
        provider: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """按查询条件检索知识数据。"""
        import faiss

        version = self.current_version()
        if version is None:
            return []
        version_dir = self.root / version
        index = faiss.read_index(str(version_dir / "index.faiss"))
        if index.ntotal == 0:
            return []
        metadata = json.loads(
            (version_dir / "metadata.json").read_text(encoding="utf-8")
        )
        vector = np.asarray(query_vector, dtype="float32").reshape(1, self.dimension)
        faiss.normalize_L2(vector)
        scores, ids = index.search(vector, min(max(top_k * 10, top_k), index.ntotal))
        results = []
        for score, vector_id in zip(scores[0], ids[0]):
            item = metadata.get(str(int(vector_id)))
            if item is None or item["tenant_id"] != tenant_id:
                continue
            if item["project_id"] not in {None, project_id}:
                continue
            if item["provider"] not in {None, provider}:
                continue
            results.append({**item, "score": float(score), "index_version": version})
            if len(results) == top_k:
                break
        return results
