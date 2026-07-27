import json

import pytest

from ci_assistant.knowledge.processing import process_document


def test_markdown_processing_masks_secrets_and_chunks_by_structure() -> None:
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
    first = process_document('{"b": 2, "a": 1}', "json")
    second = process_document('{"a":1,"b":2}', "json")

    assert first.content_hash == second.content_hash
    assert json.loads(first.normalized_content) == {"a": 1, "b": 2}


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        process_document("{", "json")

