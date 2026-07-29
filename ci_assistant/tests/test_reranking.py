import asyncio
import json

import httpx

from ci_assistant.core.config import RerankerConfig
from ci_assistant.knowledge.reranking import (
    HTTPBGEReranker,
    LocalCrossEncoderReranker,
    build_reranker,
    rerank_with_fallback,
)


def _candidates() -> list[dict]:
    """构造带 Hybrid 分数的候选知识片段。"""
    return [
        {"vector_id": 1, "content": "generic CI failure", "score": 0.9},
        {
            "vector_id": 2,
            "content": "ModuleNotFoundError requests dependency",
            "score": 0.6,
        },
    ]


def test_bge_reranker_reorders_candidates_and_preserves_hybrid_score() -> None:
    """验证 BGE 兼容响应可重排候选并保留原 Hybrid 分数。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        """返回确定性的 Cross-Encoder 排序结果。"""
        payload = json.loads(request.content)
        assert payload["model"] == "BAAI/bge-reranker-v2-m3"
        assert payload["top_n"] == 2
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.98},
                    {"index": 0, "relevance_score": 0.12},
                ]
            },
        )

    reranker = HTTPBGEReranker(
        RerankerConfig(backend="http", base_url="http://reranker.test"),
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(
        reranker.rerank("requests import error", _candidates(), top_k=2)
    )

    assert [item["vector_id"] for item in results] == [2, 1]
    assert results[0]["rerank_score"] == 0.98
    assert results[0]["hybrid_score"] == 0.6
    assert results[0]["score"] == 0.98


def test_reranker_supports_data_score_response_shape() -> None:
    """验证兼容使用 data/score 字段的 Reranker 服务。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        """返回 data/score 兼容响应。"""
        return httpx.Response(200, json={"data": [{"index": 1, "score": 0.8}]})

    reranker = HTTPBGEReranker(
        RerankerConfig(backend="http", base_url="http://reranker.test"),
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(reranker.rerank("query", _candidates(), top_k=1))

    assert results[0]["vector_id"] == 2
    assert results[0]["score"] == 0.8


def test_reranker_failure_degrades_to_hybrid_ordering() -> None:
    """验证 Reranker 不可用时保持原 Hybrid 排序和分数。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        """模拟上游服务异常。"""
        return httpx.Response(503, json={"error": "offline"})

    candidates = _candidates()
    reranker = HTTPBGEReranker(
        RerankerConfig(backend="http", base_url="http://reranker.test"),
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(
        rerank_with_fallback(reranker, "query", candidates, top_k=1)
    )

    assert results == candidates[:1]
    assert "rerank_score" not in results[0]


def test_reranker_rejects_invalid_result_index_and_degrades() -> None:
    """验证越界索引不会污染引用并会回退 Hybrid 排序。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        """返回包含越界候选索引的非法响应。"""
        return httpx.Response(
            200,
            json={"results": [{"index": 99, "relevance_score": 1.0}]},
        )

    candidates = _candidates()
    reranker = HTTPBGEReranker(
        RerankerConfig(backend="http", base_url="http://reranker.test"),
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(
        rerank_with_fallback(reranker, "query", candidates, top_k=2)
    )

    assert results == candidates


def test_local_cross_encoder_reranks_and_caches_loaded_model() -> None:
    """验证本地 CrossEncoder 重排并在同一 Worker 实例中缓存模型。"""

    class FakeCrossEncoder:
        """提供确定性 predict 结果的本地模型替身。"""

        def predict(self, pairs, **kwargs):
            """按候选顺序返回分数。"""
            assert len(pairs) == 2
            assert kwargs["batch_size"] == 8
            return [0.1, 0.95]

    loads = []

    def load_model(config):
        """记录模型加载次数。"""
        loads.append(config.model)
        return FakeCrossEncoder()

    reranker = LocalCrossEncoderReranker(
        RerankerConfig(backend="local", batch_size=8),
        model_loader=load_model,
    )

    first = asyncio.run(reranker.rerank("query", _candidates(), top_k=2))
    second = asyncio.run(reranker.rerank("query", _candidates(), top_k=1))

    assert [item["vector_id"] for item in first] == [2, 1]
    assert second[0]["vector_id"] == 2
    assert loads == ["BAAI/bge-reranker-v2-m3"]


def test_local_backend_missing_optional_dependency_degrades() -> None:
    """验证未安装 SentenceTransformers 时本地后端回退 Hybrid。"""

    def missing_loader(config):
        """模拟缺少可选依赖。"""
        raise ModuleNotFoundError("sentence_transformers")

    candidates = _candidates()
    reranker = LocalCrossEncoderReranker(
        RerankerConfig(backend="local"),
        model_loader=missing_loader,
    )

    results = asyncio.run(
        rerank_with_fallback(reranker, "query", candidates, top_k=1)
    )

    assert results == candidates[:1]


def test_build_reranker_selects_configured_backend() -> None:
    """验证工厂按 disabled、local、http 选择后端。"""
    assert build_reranker(RerankerConfig()) is None
    assert isinstance(
        build_reranker(RerankerConfig(backend="local")),
        LocalCrossEncoderReranker,
    )
    assert isinstance(
        build_reranker(RerankerConfig(backend="http")),
        HTTPBGEReranker,
    )
