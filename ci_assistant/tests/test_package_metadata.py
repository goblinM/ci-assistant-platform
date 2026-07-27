from importlib.metadata import PackageNotFoundError, version

import ci_assistant


def test_package_exposes_target_version() -> None:
    assert ci_assistant.__version__ == "0.5.0"


def test_distribution_name_when_installed() -> None:
    try:
        installed_version = version("ci-assistant-platform")
    except PackageNotFoundError:
        return

    assert installed_version == ci_assistant.__version__

