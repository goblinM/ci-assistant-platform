import asyncio

from ci_analysis_demo.schemas.analysis_schema import AnalysisLogResponse, ToolMode
from ci_analysis_demo.schemas.job_schema import AnalyzeGitlabJobRequest
from ci_analysis_demo.services import llm_service
from ci_analysis_demo.tools.base import ToolRuntimeContext
from ci_analysis_demo.tools.register import create_default_tools_executor


def _response() -> AnalysisLogResponse:
    return AnalysisLogResponse(
        error_type="unknown",
        summary="summary",
        reason="reason",
        suggestions=["suggestion"],
        confidence="low",
    )


def test_analyze_log_by_mode_dispatches_all_modes(monkeypatch):
    calls: list[str] = []

    async def fake_llm(*args, **kwargs):
        calls.append("llm")
        return _response()

    async def fake_rag(*args, **kwargs):
        calls.append("rag")
        return _response()

    async def fake_rule(*args, **kwargs):
        calls.append("rule")
        return _response()

    async def fake_autonomous(*args, **kwargs):
        calls.append("autonomous")
        return _response()

    monkeypatch.setattr(llm_service, "analyze_log_with_llm", fake_llm)
    monkeypatch.setattr(llm_service, "analyze_log_with_rag", fake_rag)
    monkeypatch.setattr(llm_service, "analyze_log_with_rag_tool", fake_rule)
    monkeypatch.setattr(llm_service, "analyze_log_with_autonomous_tools", fake_autonomous)

    cases = [
        ({"use_rag": False, "use_tools": False}, "llm"),
        ({"use_rag": True, "use_tools": False}, "rag"),
        ({"use_rag": True, "use_tools": True, "tool_mode": ToolMode.rule}, "rule"),
        ({"use_rag": True, "use_tools": True, "tool_mode": ToolMode.llm}, "autonomous"),
        ({"use_rag": True, "use_tools": True, "tool_mode": ToolMode.none}, "rag"),
    ]

    for options, expected_mode in cases:
        result = asyncio.run(llm_service.analyze_log_by_mode(
            log_text="failure",
            retriever=object(),
            tools_executor=object(),
            trace_id="trace-test",
            **options,
        ))
        assert calls[-1] == expected_mode
        assert result.extra["analysis_mode"] == {
            "llm": "llm",
            "rag": "rag",
            "rule": "rule_tools",
            "autonomous": "autonomous_tools",
        }[expected_mode]


def test_gitlab_job_reuses_dispatcher_and_forwards_mode(monkeypatch):
    captured: dict = {}

    class FakeGitLabClient:
        async def get_job(self, project_id, job_id):
            return {"name": "unit-test", "status": "failed", "stage": "test"}

        async def get_job_trace(self, project_id, job_id):
            return "ModuleNotFoundError: No module named 'requests'"

        async def get_pipeline(self, project_id, pipeline_id):
            raise AssertionError("pipeline should be fetched lazily by a tool")

    async def fake_dispatch(**kwargs):
        captured.update(kwargs)
        return _response()

    monkeypatch.setattr(llm_service, "analyze_log_by_mode", fake_dispatch)
    request = AnalyzeGitlabJobRequest(
        project_id="project-1",
        pipeline_id="pipeline-1",
        job_id="job-1",
        use_rag=False,
        use_tool=True,
        tool_mode=ToolMode.llm,
    )

    asyncio.run(llm_service.analyze_gitlab_job_log(
        data=request,
        retriever=object(),
        gitlab_client=FakeGitLabClient(),
        trace_id="trace-gitlab",
        tools_executor=object(),
    ))

    assert captured["use_rag"] is False
    assert captured["use_tools"] is True
    assert captured["tool_mode"] == ToolMode.llm
    assert captured["job_name"] == "unit-test"
    runtime_context = captured["runtime_context"]
    assert runtime_context.metadata["gitlab_bootstrap"]["pipeline_prefetched"] is False
    assert runtime_context.get_prefetched("gitlab_job", "project-1", "job-1")["name"] == "unit-test"


def test_query_job_context_reuses_request_cache():
    class CountingGitLabClient:
        def __init__(self):
            self.get_job_calls = 0

        async def get_job(self, project_id, job_id):
            self.get_job_calls += 1
            return {"id": job_id, "name": "api-job", "status": "failed"}

    client = CountingGitLabClient()
    executor = create_default_tools_executor(gitlab_client=client)
    job_tool_schema = next(
        item for item in executor.get_tools_schema()
        if item["function"]["name"] == "query_job_context"
    )
    assert "runtime_context" not in job_tool_schema["function"]["parameters"]["properties"]

    runtime_context = ToolRuntimeContext(prefetched={
        "gitlab_job": {
            ToolRuntimeContext.cache_key("project-1", "job-1"): {
                "id": "job-1",
                "name": "cached-job",
                "status": "failed",
            },
        },
    })

    cached_result = asyncio.run(executor.execute(
        tool_name="query_job_context",
        arguments={"project_id": "project-1", "job_id": "job-1"},
        runtime_context=runtime_context,
    ))

    assert cached_result.success is True
    assert cached_result.data["data_source"] == "request_cache"
    assert cached_result.data["job"]["name"] == "cached-job"
    assert client.get_job_calls == 0

    api_result = asyncio.run(executor.execute(
        tool_name="query_job_context",
        arguments={"project_id": "project-1", "job_id": "job-2"},
        runtime_context=runtime_context,
    ))

    assert api_result.data["data_source"] == "gitlab_api"
    assert client.get_job_calls == 1
