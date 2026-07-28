import asyncio
import json
from pathlib import Path

from ci_assistant.llm.gateway import RuleBasedDiagnosisGateway


def test_fixed_gitlab_jenkins_regression_set() -> None:
    """验证 ``test_fixed_gitlab_jenkins_regression_set`` 所描述的预期行为。"""
    cases = json.loads(
        (Path(__file__).parents[1] / "evaluation_cases.json").read_text(encoding="utf-8")
    )

    async def evaluate():
        """提供 ``evaluate`` 场景所需的测试替身。"""
        gateway = RuleBasedDiagnosisGateway()
        return [await gateway.diagnose(case["log"]) for case in cases]

    results = asyncio.run(evaluate())

    assert len(cases) == 18
    assert {case["provider"] for case in cases} == {"gitlab", "jenkins"}
    assert all(
        result.error_type == case["expected"]
        for result, case in zip(results, cases)
    )
    assert all(result.suggestions for result in results)

