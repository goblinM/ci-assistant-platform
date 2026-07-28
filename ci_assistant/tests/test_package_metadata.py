from importlib.metadata import distributions
from pathlib import Path
import re

import ci_assistant


def test_package_exposes_target_version() -> None:
    """验证包常量与 ``pyproject.toml`` 的发行版本一致。"""
    pyproject = (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    declared_version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"$',
        pyproject,
    )

    assert ci_assistant.__version__ == "0.6.1"
    assert declared_version is not None
    assert declared_version.group(1) == ci_assistant.__version__


def test_distribution_name_when_installed() -> None:
    """验证已安装发行元数据中包含当前项目版本。"""
    installed_versions = {
        distribution.version
        for distribution in distributions()
        if (distribution.metadata.get("Name") or "").lower().replace("_", "-")
        == "ci-assistant-platform"
    }

    if installed_versions:
        assert ci_assistant.__version__ in installed_versions
