from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_github_quality_workflow_enforces_core_checks() -> None:
    """验证 ``test_github_quality_workflow_enforces_core_checks`` 所描述的预期行为。"""
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert 'python-version: ["3.10", "3.11"]' in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m compileall -q ci_assistant ci_analysis_demo" in workflow
    assert "python -m alembic upgrade head --sql" in workflow


def test_ados_core_documentation_entries_exist() -> None:
    """验证 ``test_ados_core_documentation_entries_exist`` 所描述的预期行为。"""
    for name in (
        "DEVELOPMENT.md",
        "TODO.md",
        "DECISIONS.md",
        "DEBUG.md",
        "CHANGELOG.md",
    ):
        path = ROOT / "docs" / name
        assert path.is_file()
        assert path.read_text(encoding="utf-8").strip()
