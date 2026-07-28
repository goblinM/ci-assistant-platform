import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from ci_assistant.knowledge.processing import process_document
from ci_assistant.schemas.knowledge import CreateKnowledgeDocument


def test_markdown_processing_masks_secrets_and_chunks_by_structure() -> None:
    """验证 ``test_markdown_processing_masks_secrets_and_chunks_by_structure`` 所描述的预期行为。"""
    content = (
        "# Failure\n\nTOKEN=super-secret-value\n\n"
        "## Cause\n\nMissing dependency.\n\n"
        "## Fix\n\nInstall the dependency."
    )

    processed = process_document(content, "markdown")

    assert "super-secret-value" not in processed.normalized_content
    assert "TOKEN=***" in processed.normalized_content
    assert processed.content_hash
    assert processed.chunks


def test_json_processing_is_canonical_for_deduplication() -> None:
    """验证 ``test_json_processing_is_canonical_for_deduplication`` 所描述的预期行为。"""
    first = process_document('{"b": 2, "a": 1}', "json")
    second = process_document('{"a":1,"b":2}', "json")

    assert first.content_hash == second.content_hash
    assert json.loads(first.normalized_content) == {"a": 1, "b": 2}


def test_invalid_json_is_rejected() -> None:
    """验证 ``test_invalid_json_is_rejected`` 所描述的预期行为。"""
    with pytest.raises(ValueError, match="invalid JSON"):
        process_document("{", "json")


def test_json_document_api_does_not_bypass_file_parsers() -> None:
    """验证原 JSON 文档接口不能直接声明 PDF 格式。"""
    with pytest.raises(ValidationError):
        CreateKnowledgeDocument(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            title="Bypass attempt",
            format="pdf",
            content="not a parsed PDF",
        )
