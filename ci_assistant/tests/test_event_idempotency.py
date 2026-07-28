from ci_assistant.persistence.events import CIEventRepository


def test_event_insert_uses_database_enforced_idempotency() -> None:
    """验证 ``test_event_insert_uses_database_enforced_idempotency`` 所描述的预期行为。"""
    source_names = CIEventRepository.create_once.__code__.co_names
    assert "on_conflict_do_nothing" in source_names
    assert "returning" in source_names

