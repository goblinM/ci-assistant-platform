from __future__ import annotations

import logging


def log_task_failure(
    logger: logging.Logger,
    *,
    task_name: str,
    identifier: str,
    error_code: str,
    exception: Exception,
) -> None:
    """记录不包含异常正文和业务日志的安全任务失败事件。"""

    logger.error(
        "Worker task failed",
        extra={
            "task_name": task_name,
            "task_identifier": identifier,
            "error_code": error_code,
            "exception_type": type(exception).__name__,
        },
    )
