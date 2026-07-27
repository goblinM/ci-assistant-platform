import numpy as np

from ci_assistant.knowledge.embeddings import HashingEmbedder


def test_hashing_embeddings_are_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(128)
    first = embedder.encode(["ModuleNotFoundError requests"])
    second = embedder.encode(["ModuleNotFoundError requests"])

    assert np.array_equal(first, second)
    assert np.isclose(np.linalg.norm(first[0]), 1)

