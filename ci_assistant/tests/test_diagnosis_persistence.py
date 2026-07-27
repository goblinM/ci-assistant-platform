import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import Diagnosis


def _diagnosis() -> Diagnosis:
    return Diagnosis(
        id=uuid4(),
        tenant_id=uuid4(),
        project_id=None,
        trace_id="trace_test",
        status="queued",
        source="log",
        result=None,
        error_code=None,
    )


def test_diagnosis_lifecycle_persists_result_and_trace() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    repository = DiagnosisRepository(session)
    diagnosis = _diagnosis()

    async def run_lifecycle():
        await repository.mark_running(diagnosis)
        return await repository.mark_succeeded(
            diagnosis,
            result={"summary": "dependency missing", "references": []},
            trace={"llm_calls": 1},
            prompt_version="v1",
            model_name="test-model",
            index_version="index-1",
        )

    trace = asyncio.run(run_lifecycle())

    assert diagnosis.status == "succeeded"
    assert diagnosis.result["summary"] == "dependency missing"
    assert trace.diagnosis_id == diagnosis.id
    assert trace.trace_data == {"llm_calls": 1}
    session.add.assert_called_once_with(trace)


def test_diagnosis_failure_records_stable_error_code() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    diagnosis = _diagnosis()

    asyncio.run(
        DiagnosisRepository(session).mark_failed(diagnosis, "LLM_UNAVAILABLE")
    )

    assert diagnosis.status == "failed"
    assert diagnosis.error_code == "LLM_UNAVAILABLE"

