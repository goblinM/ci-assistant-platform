import ast
from pathlib import Path

from ci_assistant.persistence import entities  # noqa: F401
from ci_assistant.persistence.models import Base


def test_core_entities_are_registered_in_metadata() -> None:
    """验证 ``test_core_entities_are_registered_in_metadata`` 所描述的预期行为。"""
    assert {
        "tenants",
        "ci_connections",
        "projects",
        "ci_events",
        "webhook_deliveries",
        "diagnoses",
        "diagnosis_feedback",
        "analysis_traces",
        "agent_runs",
        "agent_steps",
        "action_proposals",
        "action_proposal_audits",
    }.issubset(Base.metadata.tables)


def test_initial_migration_has_revision_metadata() -> None:
    """验证 ``test_initial_migration_has_revision_metadata`` 所描述的预期行为。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260725_0001_platform_core.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "20260725_0001", "down_revision": None}


def test_webhook_delivery_migration_follows_knowledge_revision() -> None:
    """验证 Webhook 投递审计迁移追加在现有迁移历史之后。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260728_0003_webhook_deliveries.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "20260728_0003",
        "down_revision": "20260725_0002",
    }


def test_feedback_migration_follows_webhook_delivery_revision() -> None:
    """验证反馈表迁移追加在 Webhook 投递审计之后。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260729_0004_diagnosis_feedback.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "20260729_0004",
        "down_revision": "20260728_0003",
    }


def test_agent_p1_migration_follows_feedback_revision() -> None:
    """验证 Agent P1 表通过新 revision 追加到既有迁移历史。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260812_0005_agent_p1_proposals.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "20260812_0005",
        "down_revision": "20260729_0004",
    }


def test_agent_reliability_migration_follows_agent_p1_revision() -> None:
    """验证 Agent 可靠性迁移追加在 P1A/P1B revision 之后。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260824_0006_agent_reliability.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "20260824_0006",
        "down_revision": "20260812_0005",
    }


def test_agent_evidence_gap_migration_follows_reliability_revision() -> None:
    """验证证据缺口字段通过新 revision 追加到可靠性迁移之后。"""
    migration = (
        Path(__file__).parents[1]
        / "persistence"
        / "migrations"
        / "versions"
        / "20260824_0007_agent_evidence_gap.py"
    )
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "20260824_0007",
        "down_revision": "20260824_0006",
    }
