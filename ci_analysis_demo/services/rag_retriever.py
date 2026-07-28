"""
向量数据库接入？
chunk切片？Embedding优化？
top-k优化，rerank
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..schemas.rag_schema import RAGDocument, RAGResult


LEGACY_CATEGORY_ERROR_TYPES = {
    "dependency": ["dependency_missing", "dependency_conflict"],
    "private_repo": ["repo_auth_failed"],
    "test": ["test_failed"],
    "docker": ["docker_build_failed", "image_pull_failed"],
    "network": ["network_error", "timeout"],
    "env": ["env_config_error"],
    "path": ["env_config_error", "docker_build_failed"],
}

try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:
    faiss = None
    np = None
    SentenceTransformer = None


# 本地检索
class LocalRetriever:
    def __init__(self, knowledge_path: str):
        if faiss is None or np is None or SentenceTransformer is None:
            raise RuntimeError(
                "RAG dependencies are not installed. Run: pip install -r requirements.txt"
            )

        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        self.knowledge_path = Path(knowledge_path)
        with self.knowledge_path.open("r", encoding="utf-8") as f:
            raw_docs = json.load(f)

        self.docs = [self._normalize_document(doc) for doc in raw_docs]
        self._validate_documents(self.docs)

        self.doc_texts = [self._build_search_text(doc) for doc in self.docs]
        self.doc_embeddings = self.model.encode_document(self.doc_texts)
        self.doc_embeddings = np.asarray(self.doc_embeddings, dtype="float32")
        self.doc_embeddings = self._normalize(self.doc_embeddings)

        dim = self.doc_embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(self.doc_embeddings)

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.clip(norms, 1e-12, None)

    def _build_search_text(self, doc: dict) -> str:
        return "\n".join(
            [
                doc.get("title", ""),
                doc.get("content", ""),
                doc.get("category", ""),
                " ".join(doc.get("tags", [])),
                " ".join(doc.get("keywords", [])),
                " ".join(doc.get("error_types", [])),
            ]
        )

    def _normalize_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        """兼容旧知识文档，并补齐统一检索 metadata。"""
        normalized = dict(doc)
        normalized["tags"] = list(normalized.get("tags") or [])
        normalized["keywords"] = list(normalized.get("keywords") or [])
        error_types = list(normalized.get("error_types") or [])

        content = normalized.get("content", "")
        if isinstance(content, dict):
            structured_content = content
            normalized["content"] = json.dumps(content, ensure_ascii=False)
        else:
            structured_content = self._parse_structured_content(content)

        explicit_error_type = normalized.get("error_type") or structured_content.get("error_type")
        if explicit_error_type:
            error_types.append(self._normalize_error_type(str(explicit_error_type)))
        # 仅用于兼容缺少 error_types 的旧知识文档，不覆盖显式 metadata。
        if not error_types:
            error_types.extend(LEGACY_CATEGORY_ERROR_TYPES.get(normalized.get("category"), []))
        normalized["error_types"] = list(dict.fromkeys(error_types))
        return normalized

    @staticmethod
    def _parse_structured_content(content: Any) -> dict[str, Any]:
        if not isinstance(content, str) or not content.lstrip().startswith("{"):
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalize_error_type(error_type: str) -> str:
        # 别名
        aliases = {
            "private_repo_auth_failed": "repo_auth_failed",
            "pytest_collection_error": "test_failed",
            "docker_copy_missing": "docker_build_failed",
            "env_missing": "env_config_error",
        }
        return aliases.get(error_type, error_type)

    @staticmethod
    def _validate_documents(docs: list[dict[str, Any]]) -> None:
        # 校验文档
        required_fields = ("id", "title", "source", "content")
        seen_ids: set[str] = set()
        for index, doc in enumerate(docs):
            missing = [field for field in required_fields if not doc.get(field)]
            if missing:
                raise ValueError(f"knowledge document index={index} missing fields: {missing}")
            if doc["id"] in seen_ids:
                raise ValueError(f"duplicate knowledge document id: {doc['id']}")
            seen_ids.add(doc["id"])

    def metadata_match(self, doc: dict, filters: dict | None = None) -> bool:
        """
        metadata 过滤：结合 Tool/规则识别结果
        :param doc:
        :param filters:
        :return:
        """
        if not filters:
            return True

        for key, value in filters.items():
            if value is None:
                continue

            doc_value = doc.get("error_types", []) if key == "error_type" else doc.get(key)
            expected_values = set(value if isinstance(value, (list, tuple, set)) else [value])
            actual_values = set(doc_value if isinstance(doc_value, (list, tuple, set)) else [doc_value])
            if not expected_values.intersection(actual_values):
                return False

        return True

    def retrieve(
            self,
            query: str,
            top_k: int = 3,
            min_score: float = 0.25,
            filters: dict | None = None,
            candidate_multiplier: int = 4,
    ) -> RAGResult:
        """按查询条件检索知识数据。"""
        start = time.perf_counter()
        normalized_filters = filters or {}
        if not query.strip() or top_k <= 0:
            return RAGResult(
                query=query,
                filters=normalized_filters,
                top_k=max(top_k, 0),
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )

        # 三路召回：semantic、keyword、metadata，合并后再做轻量规则重排。
        query_embedding = self.model.encode_query([query])
        query_embedding = np.asarray(query_embedding, dtype="float32")
        query_embedding = self._normalize(query_embedding)
        # 获取对应要查询的top_k的数量，top_k 默认去 top_k的 candidate_multiplier倍，便于后面三路召回以及rerank重排返回数据
        candidate_k = min(len(self.docs), max(top_k, top_k * max(candidate_multiplier, 1)))
        scores, indices = self.index.search(query_embedding, candidate_k)
        # semantic：日志和知识文档表达方式不同，但含义相近的问题，直接FAISS Search中拿
        semantic_scores: dict[int, float] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and float(score) >= min_score:
                semantic_scores[int(idx)] = float(score)
        # 关键词：技术日志中很多关键内容必须精确匹配，打分
        keyword_scores = {
            idx: self.keyword_score(query, doc)
            for idx, doc in enumerate(self.docs)
        }
        keyword_indices = sorted(
            (idx for idx, score in keyword_scores.items() if score > 0),
            key=lambda idx: keyword_scores[idx],
            reverse=True,
        )[:candidate_k]
        # Metadata召回解决的是：已经通过规则识别出错误类型后，应优先查询同类型知识。
        metadata_indices = [
            idx for idx, doc in enumerate(self.docs)
            if normalized_filters and self.metadata_match(doc, normalized_filters)
        ][:candidate_k]
        # 合并：通过文档索引合并并去重
        merged_indices = list(dict.fromkeys([
            *semantic_scores.keys(),
            *keyword_indices,
            *metadata_indices,
        ]))
        candidates: list[dict[str, Any]] = []
        for idx in merged_indices:
            doc = self.docs[idx]
            metadata_matched = self.metadata_match(doc, normalized_filters)
            if normalized_filters and not metadata_matched:
                continue

            semantic_score = semantic_scores.get(idx, 0.0)
            keyword_score = keyword_scores.get(idx, 0.0)
            metadata_score = 1.0 if normalized_filters and metadata_matched else 0.0
            sources = []
            # 判断retrieval docs来源
            if idx in semantic_scores:
                sources.append("semantic")
            if idx in keyword_indices:
                sources.append("keyword")
            if idx in metadata_indices:
                sources.append("metadata")

            candidates.append({
                **doc,
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "metadata_score": metadata_score,
                "score": self.hybrid_score(semantic_score, keyword_score, metadata_score),
                "retrieval_sources": sources,
                "error_type": (doc.get("error_types") or [None])[0],
            })

        expected_error_type = normalized_filters.get("error_type")
        # rerank docs
        reranked = self.rerank_docs(candidates, query, expected_error_type)
        documents = [
            RAGDocument(
                score=item["rerank_score"],
                semantic_score=item["semantic_score"],
                keyword_score=item["keyword_score"],
                metadata_score=item["metadata_score"],
                retrieval_sources=item["retrieval_sources"],
                doc_id=item["id"],
                title=item["title"],
                content=item["content"],
                source=item["source"],
                error_type=item.get("error_type"),
                category=item.get("category", ""),
                keywords=item.get("keywords", []),
                tags=item.get("tags", []),
            )
            for item in reranked[:top_k]
        ]

        return RAGResult(
            query=query,
            filters=normalized_filters,
            top_k=top_k,
            documents=documents,
            candidate_count=len(candidates),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    def keyword_score(self, query: str, doc: dict) -> float:
        """对标题、显式关键词、标签和错误类型做归一化关键词打分。"""
        query_lower = query.lower()
        query_tokens = self._tokenize(query)
        searchable_terms = [
            *doc.get("keywords", []),
            *doc.get("tags", []),
            *doc.get("error_types", []),
            doc.get("category", ""),
        ]
        # sum 抽取击中的关键词（每击中一个就为1）
        exact_hits = sum(
            1 for term in searchable_terms
            if term and str(term).lower() in query_lower
        )
        title_tokens = self._tokenize(doc.get("title", ""))
        # 交集的长度
        title_overlap = len(query_tokens.intersection(title_tokens))
        return min(1.0, exact_hits * 0.25 + title_overlap * 0.15)

    def hybrid_score(
            self,
            vector_score: float,
            keyword_score_value: float,
            metadata_score: float = 0.0,
    ) -> float:
        """混合分数"""
        semantic = max(0.0, min(vector_score, 1.0))
        return 0.65 * semantic + 0.25 * keyword_score_value + 0.10 * metadata_score

    def rerank_docs(self, docs: list[dict], query: str, expected_error_type: str | None = None) -> list[dict]:
        """在 Hybrid 分数上增加 error type 和标题词重叠权重。"""
        reranked = []
        for doc in docs:
            score = doc.get("score", 0.0)
            if expected_error_type and expected_error_type in doc.get("error_types", []):
                score += 0.10
            title_overlap = len(self._tokenize(query).intersection(self._tokenize(doc.get("title", ""))))
            score += min(title_overlap * 0.03, 0.09)
            reranked.append({**doc, "rerank_score": round(score, 6)})
        return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]+", text)
            if token.strip()
        }

    def build_rag_query(
            self,
            log_query: str,
            primary_error: dict | None = None,
    ) -> str:
        """
        日志可能是：
            ModuleNotFoundError: No module named 'requests'
        知识库文档可能写的是：
            Python 依赖缺失排查，检查 requirements.txt 和 pip install
        可以构造一个增强 query
        :param log_query:
        :param primary_error:
        :return:
        """
        if not primary_error:
            return log_query

        error_type = primary_error.get("error_type")
        keyword = primary_error.get("keyword")
        groups = primary_error.get("groups") or []

        package_name = groups[0] if groups else None

        parts = [
            log_query,
            f"error_type: {error_type}",
            f"keyword: {keyword}",
        ]

        if package_name:
            parts.append(f"package: {package_name}")

        return "\n".join(parts)
