import ast
import re
from pathlib import Path


ROOT = Path(__file__).parents[2]


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            names.add(re.split(r"[\[<>=!~; ]", value, maxsplit=1)[0].lower())
    return names


def _project_dependency_names() -> set[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^dependencies = (\[.*?^\])", text)
    assert match is not None
    values = ast.literal_eval(match.group(1))
    return {
        re.split(r"[\[<>=!~; ]", value, maxsplit=1)[0].lower()
        for value in values
    }


def test_runtime_requirement_files_follow_pyproject_dependencies() -> None:
    """验证 ``test_runtime_requirement_files_follow_pyproject_dependencies`` 所描述的预期行为。"""
    expected = _project_dependency_names()

    assert _requirement_names(ROOT / "requirements-runtime.txt") == expected
    assert _requirement_names(ROOT / "requirements.txt") == expected


def test_sentence_transformers_is_only_an_optional_reranker_dependency() -> None:
    """验证本地 CrossEncoder 不进入默认或容器运行依赖。"""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    reranker = re.search(r"(?ms)^reranker = (\[.*?^\])", text)

    assert "sentence-transformers" not in _project_dependency_names()
    assert "sentence-transformers" not in _requirement_names(
        ROOT / "requirements-runtime.txt"
    )
    assert reranker is not None
    assert any(
        value.startswith("sentence-transformers")
        for value in ast.literal_eval(reranker.group(1))
    )
