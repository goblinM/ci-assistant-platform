"""
CI 工具函数。

历史失败记录仍使用 mock 数据；GitLab 相关工具通过 GitLabClient 调用真实 GitLab CI API，
并把冗余响应裁剪成适合放进 prompt 的必要字段。
"""
from typing import Any

from .base import ToolRuntimeContext


def query_failure_history(
    project_name: str | None = None,
    error_keyword: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """查询历史相似失败记录。当前用 mock 数据，后续可替换为数据库。"""
    mock_cases = [
        {
            "case_id": "fail_001",
            "project_name": "demo-project",
            "error_keyword": "ModuleNotFoundError",
            "error_type": "dependency_missing",
            "root_cause": "requirements.txt 缺少 requests",
            "fix": "补充 requirements.txt 并确认 CI install 阶段执行 pip install -r requirements.txt",
        },
        {
            "case_id": "fail_002",
            "project_name": "demo-project",
            "error_keyword": "403",
            "error_type": "repo_auth_failed",
            "root_cause": "私有 PyPI token 过期",
            "fix": "更新 CI 环境变量中的私有源 token",
        },
    ]

    matched = []
    for item in mock_cases:
        if project_name and item["project_name"] != project_name:
            continue
        if error_keyword and error_keyword not in item["error_keyword"]:
            continue
        if error_type and error_type != item["error_type"]:
            continue
        matched.append(item)

    return {
        "matched_count": len(matched),
        "recent_cases": matched[:3],
    }


async def query_pipeline_context(
    project_id: str | None = None,
    pipeline_id: str | None = None,
    job_name: str | None = None,
    gitlab_client=None,
) -> dict[str, Any]:
    """查询 GitLab pipeline/job 上下文。"""
    if not gitlab_client or not project_id:
        return _unavailable("missing gitlab_client or project_id", pipeline_id=pipeline_id, job_name=job_name)

    pipeline = None
    if pipeline_id:
        pipeline = await gitlab_client.get_pipeline(project_id=project_id, pipeline_id=pipeline_id)

    jobs = []
    selected_job = None
    if pipeline_id:
        jobs = await gitlab_client.list_pipeline_jobs(project_id=project_id, pipeline_id=pipeline_id)
        if job_name:
            selected_job = next((job for job in jobs if job.get("name") == job_name), None)

    return {
        "available": True,
        "pipeline": _trim_pipeline(pipeline) if pipeline else None,
        "job": _trim_job(selected_job) if selected_job else None,
        "jobs": [_trim_job(job) for job in jobs[:10]],
    }


async def query_job_context(
    job_id: str | None = None,
    project_id: str | None = None,
    gitlab_client=None,
    runtime_context: ToolRuntimeContext | None = None,
) -> dict[str, Any]:
    """查询 GitLab job 上下文。"""
    if not project_id or not job_id:
        return _unavailable("missing project_id or job_id", job_id=job_id)

    job = None
    data_source = "gitlab_api"
    if runtime_context:
        job = runtime_context.get_prefetched("gitlab_job", project_id, job_id)
        if job:
            data_source = "request_cache"

    if job is None:
        if not gitlab_client:
            return _unavailable("missing gitlab_client", job_id=job_id)
        job = await gitlab_client.get_job(project_id=project_id, job_id=job_id)
    return {
        "available": True,
        "job": _trim_job(job),
        "data_source": data_source,
    }


async def check_dependency_file(
    project_id: str | None = None,
    package_name: str | None = None,
    ref: str | None = None,
    gitlab_client=None,
) -> dict[str, Any]:
    """检查 GitLab 仓库依赖文件中是否声明指定依赖。"""
    if not gitlab_client or not project_id or not package_name:
        return _unavailable("missing gitlab_client, project_id or package_name", package_name=package_name)

    project = await gitlab_client.get_project(project_id)
    target_ref = ref or project.get("default_branch") or "main"
    checked_files = []

    for file_path in ["requirements.txt", "pyproject.toml"]:
        try:
            content = await gitlab_client.get_repository_file_raw(
                project_id=project_id,
                file_path=file_path,
                ref=target_ref,
            )
        except Exception as e:
            checked_files.append({
                "file_path": file_path,
                "exists": False,
                "error": repr(e),
            })
            continue

        package_found = package_name.lower() in content.lower()
        checked_files.append({
            "file_path": file_path,
            "exists": True,
            "package_found": package_found,
        })
        if package_found:
            break

    return {
        "available": True,
        "ref": target_ref,
        "package_name": package_name,
        "package_found": any(item.get("package_found") for item in checked_files),
        "checked_files": checked_files,
    }


async def query_recent_commits(
    project_id: str | None = None,
    branch: str | None = None,
    limit: int | None = None,
    gitlab_client=None,
) -> dict[str, Any]:
    """查询 GitLab 最近提交。"""
    if not gitlab_client or not project_id:
        return _unavailable("missing gitlab_client or project_id", branch=branch)

    commits = await gitlab_client.list_commits(
        project_id=project_id,
        ref_name=branch,
        per_page=limit or 5,
    )
    return {
        "available": True,
        "commits": [_trim_commit(commit) for commit in commits],
    }


def trim_tool_result(tool_name: str, data: dict, max_cases: int = 3) -> dict | None:
    """执行 ``trim_tool_result`` 对应的领域操作。"""
    if tool_name == "query_failure_history":
        recent_cases = data.get("recent_cases", [])
        return {
            "matched_count": data.get("matched_count", 0),
            "recent_cases": recent_cases[:max_cases],
        }

    if tool_name == "query_pipeline_context":
        return {
            "available": data.get("available"),
            "pipeline": data.get("pipeline"),
            "job": data.get("job"),
            "jobs": data.get("jobs", [])[:10],
            "reason": data.get("reason"),
        }

    if tool_name == "query_job_context":
        return {
            "available": data.get("available"),
            "job": data.get("job"),
            "data_source": data.get("data_source"),
            "reason": data.get("reason"),
        }

    if tool_name == "check_dependency_file":
        return {
            "available": data.get("available"),
            "ref": data.get("ref"),
            "package_name": data.get("package_name"),
            "package_found": data.get("package_found"),
            "checked_files": data.get("checked_files", []),
            "reason": data.get("reason"),
        }

    if tool_name == "query_recent_commits":
        return {
            "available": data.get("available"),
            "commits": data.get("commits", [])[:max_cases],
            "reason": data.get("reason"),
        }

    return data


def _unavailable(reason: str, **extra) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        **extra,
    }


def _trim_pipeline(pipeline: dict) -> dict:
    return {
        "id": pipeline.get("id"),
        "status": pipeline.get("status"),
        "ref": pipeline.get("ref"),
        "sha": pipeline.get("sha"),
        "source": pipeline.get("source"),
        "created_at": pipeline.get("created_at"),
        "updated_at": pipeline.get("updated_at"),
        "web_url": pipeline.get("web_url"),
    }


def _trim_job(job: dict) -> dict:
    runner = job.get("runner") or {}
    commit = job.get("commit") or {}
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "stage": job.get("stage"),
        "status": job.get("status"),
        "failure_reason": job.get("failure_reason"),
        "duration": job.get("duration"),
        "ref": job.get("ref"),
        "web_url": job.get("web_url"),
        "runner": {
            "id": runner.get("id"),
            "description": runner.get("description"),
            "runner_type": runner.get("runner_type"),
        } if runner else None,
        "commit": {
            "id": commit.get("id"),
            "short_id": commit.get("short_id"),
            "title": commit.get("title"),
            "message": commit.get("message"),
        } if commit else None,
    }


def _trim_commit(commit: dict) -> dict:
    return {
        "id": commit.get("id"),
        "short_id": commit.get("short_id"),
        "title": commit.get("title"),
        "message": commit.get("message"),
        "author_name": commit.get("author_name"),
        "created_at": commit.get("created_at"),
        "web_url": commit.get("web_url"),
    }
