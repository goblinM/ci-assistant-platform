import ast
from pathlib import Path

from ci_assistant.persistence import entities  # noqa: F401
from ci_assistant.persistence.models import Base


def test_core_entities_are_registered_in_metadata() -> None:
    assert {
        "tenants",
        "ci_connections",
        "projects",
        "ci_events",
        "diagnoses",
        "analysis_traces",
    }.issubset(Base.metadata.tables)


def test_initial_migration_has_revision_metadata() -> None:
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

