import logging

from ci_assistant.workers.task_logging import log_task_failure


def test_task_failure_log_uses_stable_fields_without_exception_text(caplog) -> None:
    secret = "must-not-appear"

    with caplog.at_level(logging.ERROR):
        log_task_failure(
            logging.getLogger("test.worker"),
            task_name="ci_assistant.ingest_document",
            identifier="document-id",
            error_code="KNOWLEDGE_INGESTION_FAILED",
            exception=RuntimeError(secret),
        )

    record = caplog.records[-1]
    assert record.task_name == "ci_assistant.ingest_document"
    assert record.task_identifier == "document-id"
    assert record.error_code == "KNOWLEDGE_INGESTION_FAILED"
    assert record.exception_type == "RuntimeError"
    assert secret not in caplog.text
