from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """统一不同 CI Provider 的运行和作业状态。"""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ProviderCapability(str, Enum):
    """声明 Provider 可供诊断与只读工具使用的能力。"""

    RUN_READ = "run.read"
    JOB_READ = "job.read"
    LOG_READ = "log.read"
    CHANGES_READ = "changes.read"
    REPOSITORY_READ = "repository.read"
    WEBHOOK = "webhook"


class PipelineRun(BaseModel):
    """表示跨 Provider 统一映射的流水线或工作流运行。"""

    provider: str
    connection_id: str
    project_ref: str
    run_id: str
    status: RunStatus
    branch: str | None = None
    commit_sha: str | None = None
    web_url: str | None = None


class JobRun(BaseModel):
    """表示运行中的单个构建或测试作业及其失败上下文。"""

    job_id: str
    run_id: str
    name: str
    stage: str | None = None
    status: RunStatus
    failure_reason: str | None = None
    duration_seconds: float | None = None
    agent_name: str | None = None
    web_url: str | None = None


class LogArtifact(BaseModel):
    """封装作业日志、原始长度以及是否发生安全截断。"""

    job_id: str
    content: str
    truncated: bool = False
    original_length: int = Field(ge=0)


class CommitChange(BaseModel):
    """表示与一次 CI 运行关联的统一代码变更摘要。"""

    commit_sha: str
    title: str
    message: str | None = None
    author_name: str | None = None
    web_url: str | None = None


class CIEvent(BaseModel):
    """表示已验签 Webhook 映射出的幂等 CI 事件。"""

    provider: str
    external_event_id: str
    event_type: str
    project_ref: str
    run_id: str | None = None
    job_id: str | None = None
    status: RunStatus = RunStatus.UNKNOWN
    diagnostic_reason: str | None = None
