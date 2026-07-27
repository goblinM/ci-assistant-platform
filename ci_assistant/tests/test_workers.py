from unittest.mock import MagicMock

from ci_assistant.core.config import load_settings
from ci_assistant.workers.celery_app import create_celery_app


def test_worker_uses_redis_and_reliable_delivery_settings() -> None:
    fake_app = MagicMock()
    factory = MagicMock(return_value=fake_app)
    settings = load_settings(environ={"REDIS_URL": "redis://queue.example:6379/2"})

    result = create_celery_app(settings, celery_factory=factory)

    assert result is fake_app
    factory.assert_called_once_with(
        "ci_assistant",
        broker="redis://queue.example:6379/2",
        backend="redis://queue.example:6379/2",
        include=[
            "ci_assistant.workers.diagnosis_tasks",
            "ci_assistant.workers.ingestion_tasks",
        ],
    )
    configured = fake_app.conf.update.call_args.kwargs
    assert configured["task_acks_late"] is True
    assert configured["task_reject_on_worker_lost"] is True
    assert configured["broker_connection_retry_on_startup"] is True

