from __future__ import annotations

from typing import Any, Callable

from ci_assistant.core.config import PlatformSettings, load_settings


def create_celery_app(
    settings: PlatformSettings | None = None,
    *,
    celery_factory: Callable[..., Any] | None = None,
) -> Any:
    """Create the worker app without importing Celery during API-only startup."""

    if celery_factory is None:
        from celery import Celery

        celery_factory = Celery

    resolved = settings or load_settings()
    broker_url = resolved.redis.url.get_secret_value()
    app = celery_factory(
        "ci_assistant",
        broker=broker_url,
        backend=broker_url,
        include=[
            "ci_assistant.workers.diagnosis_tasks",
            "ci_assistant.workers.ingestion_tasks",
        ],
    )
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        result_expires=86400,
        task_default_retry_delay=5,
        task_routes={
            "ci_assistant.diagnose": {"queue": "diagnosis"},
            "ci_assistant.ingest_document": {"queue": "knowledge"},
            "ci_assistant.reindex_knowledge": {"queue": "knowledge"},
        },
    )
    return app


try:
    app = create_celery_app()
except ModuleNotFoundError:
    app = None
