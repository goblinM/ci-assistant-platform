import sqlite3

import numpy as np

from ci_assistant.knowledge.embeddings import (
    CachedEmbedder,
    HashingEmbedder,
    SQLiteEmbeddingCache,
)


class CountingEmbedder:
    """记录实际计算文本数量的 Embedder 替身。"""

    def __init__(self) -> None:
        self.inner = HashingEmbedder(64)
        self.encoded_texts = 0

    def encode(self, texts, *, normalize_embeddings=True):
        """统计后委托给确定性 Hashing Embedder。"""
        self.encoded_texts += len(texts)
        return self.inner.encode(
            texts,
            normalize_embeddings=normalize_embeddings,
        )

    def get_sentence_embedding_dimension(self):
        """返回测试向量维度。"""
        return 64


def test_embedding_cache_reuses_vectors_without_storing_text(tmp_path) -> None:
    """验证重复文本命中持久化缓存且 SQLite 不保存原文。"""
    path = tmp_path / "embeddings.sqlite3"
    inner = CountingEmbedder()
    embedder = CachedEmbedder(
        inner,
        SQLiteEmbeddingCache(path),
        model_name="test-model",
    )

    first = embedder.encode(["sensitive internal document", "second"])
    second = embedder.encode(["sensitive internal document", "second"])

    assert inner.encoded_texts == 2
    assert np.allclose(first, second)
    assert b"sensitive internal document" not in path.read_bytes()


def test_embedding_cache_namespace_includes_normalization(tmp_path) -> None:
    """验证归一化参数不同不会错误复用向量。"""
    inner = CountingEmbedder()
    embedder = CachedEmbedder(
        inner,
        SQLiteEmbeddingCache(tmp_path / "cache.sqlite3"),
        model_name="test-model",
    )

    embedder.encode(["same"], normalize_embeddings=True)
    embedder.encode(["same"], normalize_embeddings=False)

    assert inner.encoded_texts == 2


def test_embedding_cache_evicts_oldest_entries(tmp_path) -> None:
    """验证缓存超过上限时按最近访问时间淘汰旧项。"""
    path = tmp_path / "cache.sqlite3"
    embedder = CachedEmbedder(
        CountingEmbedder(),
        SQLiteEmbeddingCache(path, max_entries=2),
        model_name="test-model",
    )

    embedder.encode(["one", "two", "three"])

    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert count == 2


def test_embedding_cache_filesystem_failure_falls_back(
    tmp_path,
    monkeypatch,
) -> None:
    """验证缓存文件系统异常时仍返回实时计算向量。"""
    inner = CountingEmbedder()
    cache = SQLiteEmbeddingCache(tmp_path / "cache.sqlite3")

    def fail_connect():
        """模拟缓存目录或文件不可访问。"""
        raise OSError("read-only filesystem")

    monkeypatch.setattr(cache, "_connect", fail_connect)
    embedder = CachedEmbedder(inner, cache, model_name="test-model")

    result = embedder.encode(["fallback"])

    assert result.shape == (1, 64)
    assert inner.encoded_texts == 1
