from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from ci_assistant.core.config import RerankerConfig


logger = logging.getLogger(__name__)
_LOCAL_MODEL_CACHE: dict[tuple[str, str, int, str | None, bool], Any] = {}


class RerankerError(RuntimeError):
    """表示 Reranker 不可用或响应不符合契约。"""


class Reranker(Protocol):
    """统一本地和 HTTP Cross-Encoder 后端契约。"""

    config: RerankerConfig

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """对已通过 ACL 的候选重新评分，并按相关性降序返回 Top K。"""
        ...


def _rank_candidates(
    candidates: list[dict[str, Any]],
    indexed_scores: list[tuple[int, float]],
    top_k: int,
) -> list[dict[str, Any]]:
    """校验候选索引和分数，并映射为统一重排结果。"""
    ranked: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, score in indexed_scores:
        if (
            not isinstance(index, int)
            or index < 0
            or index >= len(candidates)
            or index in seen
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise RerankerError("Reranker result index or score is invalid")
        seen.add(index)
        candidate = dict(candidates[index])
        candidate["hybrid_score"] = candidate.get("score", 0.0)
        candidate["rerank_score"] = float(score)
        candidate["score"] = float(score)
        ranked.append(candidate)
        if len(ranked) == top_k:
            break
    if not ranked:
        raise RerankerError("Reranker produced no ranked candidates")
    return ranked


class HTTPBGEReranker:
    """调用兼容 `/rerank` 契约的独立 Cross-Encoder/BGE 服务。"""

    def __init__(
        self,
        config: RerankerConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """通过 HTTP 服务按 Cross-Encoder 分数重排知识片段。"""
        if not candidates or top_k <= 0:
            return []
        headers = {"Content-Type": "application/json"}
        api_key = self.config.api_key.get_secret_value()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.config.model,
            "query": query,
            "documents": [item.get("content", "") for item in candidates],
            "top_n": min(top_k, len(candidates)),
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = await client.post(
                    f"{self.config.base_url}{self.config.endpoint}",
                    headers=headers,
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise RerankerError("Reranker request failed") from exc
        if response.status_code >= 400:
            raise RerankerError(
                f"Reranker returned HTTP {response.status_code}"
            )
        return self._map_response(response.json(), candidates, top_k)

    @staticmethod
    def _map_response(
        payload: Any,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """校验常见 BGE/Jina 响应并映射回原候选元数据。"""
        if not isinstance(payload, dict):
            raise RerankerError("Reranker response must be an object")
        results = payload.get("results")
        if results is None:
            results = payload.get("data")
        if not isinstance(results, list) or not results:
            raise RerankerError("Reranker response has no results")

        indexed_scores: list[tuple[int, float]] = []
        for result in results:
            if not isinstance(result, dict):
                raise RerankerError("Reranker result must be an object")
            index = result.get("index")
            score = result.get("relevance_score", result.get("score"))
            indexed_scores.append((index, score))
        return _rank_candidates(candidates, indexed_scores, top_k)


class LocalCrossEncoderReranker:
    """使用 SentenceTransformers CrossEncoder 在 Worker 进程内重排。"""

    def __init__(
        self,
        config: RerankerConfig,
        *,
        model_loader: Callable[[RerankerConfig], Any] | None = None,
    ) -> None:
        self.config = config
        self.model_loader = model_loader
        self._model: Any | None = None

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """在线程中执行本地 CrossEncoder 推理，避免阻塞 Worker 事件循环。"""
        if not candidates or top_k <= 0:
            return []
        try:
            model = await asyncio.to_thread(self._load_model)
            pairs = [
                [query, str(candidate.get("content", ""))]
                for candidate in candidates
            ]
            scores = await asyncio.to_thread(
                model.predict,
                pairs,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except (ImportError, ModuleNotFoundError) as exc:
            raise RerankerError(
                "Local reranker requires the 'reranker' optional dependency"
            ) from exc
        except Exception as exc:
            raise RerankerError("Local reranker inference failed") from exc

        values = scores.tolist() if hasattr(scores, "tolist") else list(scores)
        if len(values) != len(candidates):
            raise RerankerError("Local reranker score count does not match candidates")
        indexed_scores = sorted(
            enumerate(float(value) for value in values),
            key=lambda item: item[1],
            reverse=True,
        )
        return _rank_candidates(candidates, indexed_scores, top_k)

    def _load_model(self) -> Any:
        """懒加载并按 Worker 进程缓存本地 CrossEncoder 模型。"""
        if self._model is not None:
            return self._model
        if self.model_loader is not None:
            self._model = self.model_loader(self.config)
            return self._model
        key = (
            self.config.model,
            self.config.device,
            self.config.max_length,
            self.config.revision,
            self.config.local_files_only,
        )
        cached = _LOCAL_MODEL_CACHE.get(key)
        if cached is not None:
            self._model = cached
            return cached
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(
            self.config.model,
            device=self.config.device,
            max_length=self.config.max_length,
            revision=self.config.revision,
            local_files_only=self.config.local_files_only,
            trust_remote_code=False,
        )
        _LOCAL_MODEL_CACHE[key] = model
        self._model = model
        return model


async def rerank_with_fallback(
    reranker: Reranker | None,
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """在任一 Reranker 后端异常时安全降级为原 Hybrid 排序。"""
    fallback = candidates[:top_k]
    if reranker is None:
        return fallback
    try:
        return await reranker.rerank(query, candidates, top_k=top_k)
    except (RerankerError, ValueError, TypeError):
        logger.warning(
            "Reranker degraded to hybrid ordering",
            extra={
                "reranker_backend": reranker.config.backend,
                "reranker_model": reranker.config.model,
            },
        )
        return fallback


def build_reranker(config: RerankerConfig) -> Reranker | None:
    """按配置构建 disabled、local 或 http Reranker。"""
    if config.backend == "local":
        return LocalCrossEncoderReranker(config)
    if config.backend == "http":
        return HTTPBGEReranker(config)
    return None
