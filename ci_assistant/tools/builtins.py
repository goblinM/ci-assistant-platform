from __future__ import annotations

from typing import Any

from ci_assistant.providers.base import CIProvider


async def get_run_context(
    provider: CIProvider, *, project_ref: str, run_id: str
) -> dict[str, Any]:
    """获取 ``get_run_context`` 对应的数据。"""
    run = await provider.get_run(project_ref, run_id)
    jobs = await provider.list_jobs(project_ref, run_id)
    return {
        "run": run.model_dump(mode="json"),
        "jobs": [job.model_dump(mode="json") for job in jobs[:20]],
    }


async def get_job_context(
    provider: CIProvider, *, project_ref: str, job_id: str
) -> dict[str, Any]:
    """获取 ``get_job_context`` 对应的数据。"""
    job = await provider.get_job(project_ref, job_id)
    return {"job": job.model_dump(mode="json")}


async def get_job_log(
    provider: CIProvider, *, project_ref: str, job_id: str
) -> dict[str, Any]:
    """获取 ``get_job_log`` 对应的数据。"""
    log = await provider.get_job_log(project_ref, job_id)
    return {"log": log.model_dump(mode="json")}


async def get_changes(
    provider: CIProvider, *, project_ref: str, run_id: str
) -> dict[str, Any]:
    """获取 ``get_changes`` 对应的数据。"""
    changes = await provider.list_changes(project_ref, run_id)
    return {"changes": [change.model_dump(mode="json") for change in changes[:20]]}

