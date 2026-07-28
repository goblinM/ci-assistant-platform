from pathlib import Path

import yaml


def test_compose_contains_platform_services_and_healthchecks() -> None:
    """验证 ``test_compose_contains_platform_services_and_healthchecks`` 所描述的预期行为。"""
    compose_path = Path(__file__).parents[2] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert {"api", "worker", "migrate", "postgres", "redis"} <= services.keys()
    assert services["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["postgres"]["healthcheck"]
    assert services["redis"]["healthcheck"]
    assert "--queues=diagnosis,knowledge" in services["worker"]["command"]

