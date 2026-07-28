import numpy as np

from ci_assistant.knowledge.index import FaissIndexStore, IndexedChunk
from ci_assistant.knowledge.retrieval import HybridRetriever


def test_hybrid_retrieval_combines_semantic_keyword_and_metadata(tmp_path) -> None:
    """验证 ``test_hybrid_retrieval_combines_semantic_keyword_and_metadata`` 所描述的预期行为。"""
    store = FaissIndexStore(tmp_path, 2)
    store.publish(
        version="v1",
        vectors=np.asarray([[1, 0], [1, 0]], dtype="float32"),
        chunks=[
            IndexedChunk(1, "generic failure", "t", None, None, {}),
            IndexedChunk(
                2,
                "ModuleNotFoundError requests",
                "t",
                "p",
                "gitlab",
                {},
            ),
        ],
    )
    results = HybridRetriever(store).retrieve(
        query_vector=np.asarray([1, 0], dtype="float32"),
        query_text="ModuleNotFoundError requests",
        tenant_id="t",
        project_id="p",
        provider="gitlab",
        top_k=2,
    )

    assert results[0]["vector_id"] == 2
    assert results[0]["keyword_score"] == 1
    assert results[0]["metadata_score"] == 0.2

