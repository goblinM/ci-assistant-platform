import numpy as np

from ci_assistant.knowledge.embeddings import HashingEmbedder


def test_hashing_embeddings_are_deterministic_and_normalized() -> None:
    """验证 ``test_hashing_embeddings_are_deterministic_and_normalized`` 所描述的预期行为。"""
    embedder = HashingEmbedder(128)
    first = embedder.encode(["ModuleNotFoundError requests"])
    second = embedder.encode(["ModuleNotFoundError requests"])

    assert np.array_equal(first, second)
    assert np.isclose(np.linalg.norm(first[0]), 1)

