from ci_analysis_demo.schemas.rag_schema import RAGDocument, RAGResult
from ci_analysis_demo.schemas.trace_schema import AnalysisTrace
from ci_analysis_demo.services.llm_service import _record_rag_trace
from ci_analysis_demo.services.log_query_service import build_rag_filters, extract_query_from_log
from ci_analysis_demo.services.rag_retriever import LocalRetriever


def test_extract_query_removes_noise_and_deduplicates_errors():
    log_text = """2026-07-16 10:00:00 INFO install dependencies
2026-07-16 10:00:01 ModuleNotFoundError: No module named 'requests'
2026-07-16 10:00:01 ModuleNotFoundError: No module named 'requests'
"""

    query = extract_query_from_log(log_text)

    assert query == "ModuleNotFoundError: No module named 'requests'"


def test_build_rag_filters_uses_primary_error():
    filters = build_rag_filters("ModuleNotFoundError: No module named 'requests'")

    assert filters == {"error_type": "dependency_missing"}


def test_document_normalization_prefers_explicit_metadata():
    retriever = LocalRetriever.__new__(LocalRetriever)
    document = retriever._normalize_document({
        "id": "docs-test",
        "title": "Dependency failure",
        "source": "test",
        "content": "failure notes",
        "category": "dependency",
        "error_types": ["dependency_missing"],
        "keywords": ["ModuleNotFoundError"],
    })

    assert document["error_types"] == ["dependency_missing"]
    assert retriever.metadata_match(document, {"error_type": "dependency_missing"})
    assert not retriever.metadata_match(document, {"error_type": "timeout"})


def test_keyword_and_rule_rerank_prioritize_exact_error_type():
    retriever = LocalRetriever.__new__(LocalRetriever)
    query = "ModuleNotFoundError requests dependency_missing"
    dependency_doc = {
        "title": "ModuleNotFoundError dependency guide",
        "keywords": ["ModuleNotFoundError", "requests"],
        "tags": ["python"],
        "error_types": ["dependency_missing"],
        "category": "dependency",
        "score": 0.5,
    }
    generic_doc = {
        "title": "CI troubleshooting",
        "keywords": ["CI"],
        "tags": ["manual"],
        "error_types": [],
        "category": "manual",
        "score": 0.55,
    }

    assert retriever.keyword_score(query, dependency_doc) > retriever.keyword_score(query, generic_doc)
    reranked = retriever.rerank_docs(
        [generic_doc, dependency_doc],
        query,
        expected_error_type="dependency_missing",
    )
    assert reranked[0]["title"] == dependency_doc["title"]


def test_query_rewrite_adds_shared_primary_error_context():
    retriever = LocalRetriever.__new__(LocalRetriever)
    rewritten = retriever.build_rag_query(
        "ModuleNotFoundError: No module named 'requests'",
        {
            "error_type": "dependency_missing",
            "keyword": "ModuleNotFoundError",
            "groups": ["requests"],
        },
    )

    assert "error_type: dependency_missing" in rewritten
    assert "package: requests" in rewritten


def test_rag_result_applies_context_budget_and_builds_references():
    result = RAGResult(
        query="dependency failure",
        filters={"error_type": "dependency_missing"},
        top_k=1,
        candidate_count=3,
        documents=[RAGDocument(
            doc_id="docs-001",
            title="Dependency guide",
            source="manual",
            content="x" * 1000,
            score=0.9,
            error_type="dependency_missing",
            category="dependency",
            tags=["python"],
        )],
    )

    context = result.to_prompt_context(max_chars=240)

    assert len(context) <= 240
    assert result.hit_doc_ids == ["docs-001"]
    assert result.to_references()[0]["id"] == "docs-001"

    trace = AnalysisTrace(trace_id="trace-test")
    _record_rag_trace(trace, result, context_max_chars=240)
    assert trace.extra["rag"]["candidate_count"] == 3
    assert trace.extra["rag"]["context_length"] <= 240
