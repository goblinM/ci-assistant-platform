from importlib.metadata import PackageNotFoundError, version

import ci_assistant


def test_package_exposes_target_version() -> None:
    """验证 ``test_package_exposes_target_version`` 所描述的预期行为。"""
    assert ci_assistant.__version__ == "0.5.0"


def test_distribution_name_when_installed() -> None:
    """验证 ``test_distribution_name_when_installed`` 所描述的预期行为。"""
    try:
        installed_version = version("ci-assistant-platform")
    except PackageNotFoundError:
        return

    assert installed_version == ci_assistant.__version__

