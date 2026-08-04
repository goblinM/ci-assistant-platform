from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Protocol

import numpy as np

from ci_assistant.core.config import KnowledgeConfig


logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """定义知识索引所需的批量文本向量与维度查询契约。"""

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """按输入顺序生成二维文本向量矩阵，并可执行归一化。"""
        ...

    def get_sentence_embedding_dimension(self) -> int:
        """返回当前向量模型为每段输入文本生成的固定向量维度。"""
        ...


class HashingEmbedder:
    """提供无需下载模型或 GPU 的确定性本地哈希向量。"""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """通过稳定 Token 哈希生成可选归一化向量，用于离线和降级场景。"""
        matrix = np.zeros((len(texts), self.dimension), dtype="float32")
        for row, text in enumerate(texts):
            for token in re.findall(r"[\w.-]+", text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                column = value % self.dimension
                matrix[row, column] += -1.0 if value & 1 else 1.0
        if normalize_embeddings and len(texts):
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            matrix /= np.where(norms == 0, 1, norms)
        return matrix

    def get_sentence_embedding_dimension(self) -> int:
        """返回本地哈希向量器为每段文本配置的固定向量维度。"""
        return self.dimension


class SQLiteEmbeddingCache:
    """使用 SQLite/WAL 持久化不含原文的 Embedding Cache。"""

    def __init__(self, path: Path, *, max_entries: int = 100_000) -> None:
        self.path = path
        self.max_entries = max_entries

    def get_many(
        self,
        keys: list[str],
        *,
        dimension: int,
    ) -> dict[str, np.ndarray]:
        """批量读取并校验缓存向量；缓存损坏或不可用时返回空命中。"""
        if not keys:
            return {}
        try:
            rows = []
            with closing(self._connect()) as connection, connection:
                for offset in range(0, len(keys), 500):
                    batch = keys[offset : offset + 500]
                    placeholders = ",".join("?" for _ in batch)
                    rows.extend(
                        connection.execute(
                            f"SELECT cache_key, vector FROM embeddings "
                            f"WHERE cache_key IN ({placeholders})",
                            batch,
                        ).fetchall()
                    )
                now = int(time.time())
                connection.executemany(
                    "UPDATE embeddings SET accessed_at = ? WHERE cache_key = ?",
                    [(now, key) for key, _ in rows],
                )
        except (OSError, sqlite3.DatabaseError):
            logger.warning("Embedding cache read failed; computing without cache")
            return {}
        values: dict[str, np.ndarray] = {}
        for key, payload in rows:
            vector = np.frombuffer(payload, dtype="float32").copy()
            if vector.shape == (dimension,) and np.isfinite(vector).all():
                values[key] = vector
        return values

    def put_many(self, values: dict[str, np.ndarray]) -> None:
        """批量写入向量并按最近访问时间限制缓存规模。"""
        if not values:
            return
        now = int(time.time())
        rows = [
            (key, np.asarray(vector, dtype="float32").tobytes(), now, now)
            for key, vector in values.items()
        ]
        try:
            with closing(self._connect()) as connection, connection:
                connection.executemany(
                    """
                    INSERT INTO embeddings(cache_key, vector, created_at, accessed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        vector = excluded.vector,
                        accessed_at = excluded.accessed_at
                    """,
                    rows,
                )
                count = connection.execute(
                    "SELECT COUNT(*) FROM embeddings"
                ).fetchone()[0]
                overflow = int(count) - self.max_entries
                if overflow > 0:
                    connection.execute(
                        """
                        DELETE FROM embeddings
                        WHERE cache_key IN (
                            SELECT cache_key FROM embeddings
                            ORDER BY accessed_at ASC
                            LIMIT ?
                        )
                        """,
                        (overflow,),
                    )
        except (OSError, sqlite3.DatabaseError):
            logger.warning("Embedding cache write failed; continuing without cache")

    def _connect(self) -> sqlite3.Connection:
        """创建启用 WAL 的短生命周期 SQLite 连接。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                accessed_at INTEGER NOT NULL
            )
            """
        )
        return connection


class CachedEmbedder:
    """使用模型、参数和文本哈希复用 Embedding 结果。"""

    def __init__(
        self,
        embedder: Embedder,
        cache: SQLiteEmbeddingCache,
        *,
        model_name: str,
    ) -> None:
        self.embedder = embedder
        self.cache = cache
        self.model_name = model_name

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """按输入顺序合并缓存命中与实时计算结果，并写回缺失向量。"""
        dimension = self.get_sentence_embedding_dimension()
        keys = [
            self._cache_key(text, dimension, normalize_embeddings)
            for text in texts
        ]
        cached = self.cache.get_many(keys, dimension=dimension)
        missing_positions = [
            index for index, key in enumerate(keys) if key not in cached
        ]
        if missing_positions:
            missing_texts = [texts[index] for index in missing_positions]
            computed = self.embedder.encode(
                missing_texts,
                normalize_embeddings=normalize_embeddings,
            )
            self.cache.put_many(
                {
                    keys[position]: computed[offset]
                    for offset, position in enumerate(missing_positions)
                }
            )
            cached.update(
                {
                    keys[position]: np.asarray(computed[offset], dtype="float32")
                    for offset, position in enumerate(missing_positions)
                }
            )
        if not texts:
            return np.empty((0, dimension), dtype="float32")
        return np.stack([cached[key] for key in keys]).astype("float32")

    def get_sentence_embedding_dimension(self) -> int:
        """返回缓存所代理的底层向量模型声明的固定向量维度。"""
        return self.embedder.get_sentence_embedding_dimension()

    def _cache_key(
        self,
        text: str,
        dimension: int,
        normalize_embeddings: bool,
    ) -> str:
        """使用模型、维度、归一化参数和文本哈希生成不含原文的稳定缓存键。"""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        namespace = (
            f"{self.model_name}:{dimension}:{int(normalize_embeddings)}:{digest}"
        )
        return hashlib.sha256(namespace.encode("utf-8")).hexdigest()


def build_embedder(config: KnowledgeConfig) -> Embedder:
    """构建默认 Hashing Embedder，并按配置启用持久化缓存。"""
    embedder: Embedder = HashingEmbedder(config.embedding_dimension)
    if not config.embedding_cache_enabled:
        return embedder
    cache_path = (
        config.embedding_cache_path
        or config.storage_path / "embedding-cache" / "embeddings.sqlite3"
    )
    return CachedEmbedder(
        embedder,
        SQLiteEmbeddingCache(
            cache_path,
            max_entries=config.embedding_cache_max_entries,
        ),
        model_name=config.embedding_model,
    )
