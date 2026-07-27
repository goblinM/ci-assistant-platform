from __future__ import annotations

import hashlib
import re

import numpy as np


class HashingEmbedder:
    """Deterministic local embedding with no model download or GPU runtime."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
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
        return self.dimension

