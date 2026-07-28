import numpy as np

from ci_assistant.knowledge.index import FaissIndexStore, IndexedChunk


def test_faiss_index_publishes_atomically_and_enforces_acl(tmp_path) -> None:
    """验证 ``test_faiss_index_publishes_atomically_and_enforces_acl`` 所描述的预期行为。"""
    store = FaissIndexStore(tmp_path / "indexes", dimension=2)
    chunks = [
        IndexedChunk(1, "tenant-a global", "tenant-a", None, None, {}),
        IndexedChunk(2, "tenant-b private", "tenant-b", "project-b", "gitlab", {}),
        IndexedChunk(3, "tenant-a project", "tenant-a", "project-a", "gitlab", {}),
    ]
    store.publish(
        version="v1",
        vectors=np.asarray([[1, 0], [1, 0], [1, 0]], dtype="float32"),
        chunks=chunks,
    )

    results = store.search(
        np.asarray([1, 0], dtype="float32"),
        tenant_id="tenant-a",
        project_id="project-a",
        provider="gitlab",
        top_k=10,
    )

    assert store.current_version() == "v1"
    assert {item["vector_id"] for item in results} == {1, 3}
    assert all(item["tenant_id"] == "tenant-a" for item in results)
    assert not (tmp_path / "indexes" / ".CURRENT.tmp").exists()


def test_empty_index_version_removes_all_previous_results(tmp_path) -> None:
    """验证 ``test_empty_index_version_removes_all_previous_results`` 所描述的预期行为。"""
    store = FaissIndexStore(tmp_path / "indexes", dimension=2)
    store.publish(
        version="v1",
        vectors=np.asarray([[1, 0]], dtype="float32"),
        chunks=[IndexedChunk(1, "old", "tenant", None, None, {})],
    )
    store.publish(
        version="v2",
        vectors=np.empty((0, 2), dtype="float32"),
        chunks=[],
    )

    assert store.current_version() == "v2"
    assert (
        store.search(
            np.asarray([1, 0], dtype="float32"),
            tenant_id="tenant",
            project_id=None,
            provider=None,
        )
        == []
    )
