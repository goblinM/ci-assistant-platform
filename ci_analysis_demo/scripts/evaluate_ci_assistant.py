import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd
import httpx
from pydantic import ValidationError

try:
    from ci_analysis_demo.schemas.analysis import AnalysisLogResponse
except ModuleNotFoundError:
    from schemas.analysis import AnalysisLogResponse

API_URL = "http://127.0.0.1:8080/ci/analyze-log"
RAG_API_URL = "http://127.0.0.1:8080/ci/analyze-rag-log"
EVAL_CASE_PATH = Path(__file__).resolve().parents[1] / "knowledge_docs" / "eval_cases.json"
SUPPORTED_ERROR_TYPES = set(AnalysisLogResponse.model_fields["error_type"].annotation.__args__)


def load_cases(path: str) -> list[dict[str, Any]]:
    """解析或加载 ``load_cases`` 对应的数据。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def keyword_score(text: str, expected_keywords: list[str]) -> float:
    """
    关键词覆盖率：输出的 reason/suggestions 是否包含期望关键词。
    :param text:
    :param expected_keywords:
    :return:
    """
    if not expected_keywords:
        return 1.0

    matched = 0
    lower_text = text.lower()

    for keyword in expected_keywords:
        if keyword.lower() in lower_text:
            matched += 1

    return matched / len(expected_keywords)


def _get_field(item: Any, field: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def reference_hit(references, expected_titles: list[str]) -> bool:
    """
    Top-3检索命中率：返回的 references 里是否包含 expected_reference_titles
    :param references:
    :param expected_titles:
    :return:
    """
    if not expected_titles:
        return True

    if not references:
        return False

    actual_titles = [title.strip() for title in reference_titles(references)]

    for expected in expected_titles:
        expected = expected.strip()
        if any(expected == actual or expected in actual or actual in expected for actual in actual_titles):
            return True

    return False


def reference_titles(references) -> list[str]:
    """执行 ``reference_titles`` 对应的领域操作。"""
    if not references:
        return []
    return [_get_field(ref, "title", "") for ref in references]


async def evaluate_one(client: httpx.AsyncClient, case: dict[str, Any], api_url: str) -> dict[str, Any]:
    """执行 ``evaluate_one`` 对应的领域操作。"""
    case_id = case["case_id"]

    try:
        resp = await client.post(
            api_url,
            json={
                "log_text": case["log_text"],
                "project_name": "demo-project"
            },
            timeout=60,
        )

        status_code = resp.status_code
        content_type = resp.headers.get("content-type", "")
        response_text = resp.text
        try:
            raw_json = resp.json()
        except json.JSONDecodeError:
            return {
                "case_id": case_id,
                "status_code": status_code,
                "content_type": content_type,
                "schema_valid": False,
                "error_type_correct": False,
                "reference_hit": False,
                "keyword_score": 0,
                "error": "response_is_not_json",
                "response_text": response_text[:500],
            }

        if status_code != 200:
            return {
                "case_id": case_id,
                "status_code": status_code,
                "content_type": content_type,
                "schema_valid": False,
                "error_type_correct": False,
                "reference_hit": False,
                "keyword_score": 0,
                "error": raw_json,
            }

        result = AnalysisLogResponse.model_validate(raw_json)

        output_text = (
                result.summary + "\n"
                + result.reason + "\n"
                + "\n".join(result.suggestions)
        )
        actual_error_type = result.error_type
        actual_reference_titles = reference_titles(result.references)
        return {
            "case_id": case_id,
            "status_code": status_code,
            "content_type": content_type,
            "schema_valid": True,
            "expected_error_type": case["expected_error_type"],
            "actual_error_type": actual_error_type,
            "error_type_correct": actual_error_type == case["expected_error_type"],
            "reference_hit": reference_hit(result.references, case.get("expected_reference_titles", [])),
            "expected_reference_titles": case.get("expected_reference_titles", []),
            "actual_reference_titles": actual_reference_titles,
            "keyword_score": keyword_score(output_text, case.get("expected_keywords", [])),
            "confidence": result.confidence,
            "summary": result.summary,
            "error": "",
        }

    except ValidationError as e:
        return {
            "case_id": case_id,
            "schema_valid": False,
            "error_type_correct": False,
            "reference_hit": False,
            "keyword_score": 0,
            "error": f"schema_error: {e}",
        }
    except Exception as e:
        return {
            "case_id": case_id,
            "schema_valid": False,
            "error_type_correct": False,
            "reference_hit": False,
            "keyword_score": 0,
            "error": repr(e),
        }


async def main(use_rag: bool = False):
    """运行当前模块的命令行入口。"""
    print(EVAL_CASE_PATH)
    cases = load_cases(EVAL_CASE_PATH)
    print(f"Loaded cases: {len(cases)}")
    unsupported_expected_types = sorted(
        {
            case["expected_error_type"]
            for case in cases
            if case["expected_error_type"] not in SUPPORTED_ERROR_TYPES
        }
    )
    if use_rag:
        api_url = RAG_API_URL
    else:
        api_url = API_URL
    print(f"Evaluating API: {api_url}")
    # 本地评测不要继承 HTTP_PROXY/HTTPS_PROXY，否则 127.0.0.1 可能被代理成空 502。
    async with httpx.AsyncClient(trust_env=False) as client:
        rows = []
        for case in cases:
            await asyncio.sleep(1)
            row = await evaluate_one(client, case, api_url=api_url)
            rows.append(row)
    failed_rows = [row for row in rows if not row.get("schema_valid")]
    if failed_rows:
        print("First failed rows:")
        for row in failed_rows[:3]:
            print(row)
    reference_miss_rows = [row for row in rows if row.get("schema_valid") and not row.get("reference_hit")]
    if reference_miss_rows:
        print("First reference miss rows:")
        for row in reference_miss_rows[:5]:
            print(
                {
                    "case_id": row.get("case_id"),
                    "expected_reference_titles": row.get("expected_reference_titles"),
                    "actual_reference_titles": row.get("actual_reference_titles"),
                }
            )
    df = pd.DataFrame(rows)

    total = len(df)
    schema_valid_rate = df["schema_valid"].mean()
    error_type_accuracy = df["error_type_correct"].mean()
    reference_hit_rate = df["reference_hit"].mean()
    avg_keyword_score = df["keyword_score"].mean()

    print("====== Evaluation Summary ======")
    print(f"Total cases: {total}")
    print(f"Schema valid rate: {schema_valid_rate:.2%}")
    print(f"Error type accuracy: {error_type_accuracy:.2%}")
    print(f"Top-k reference hit rate: {reference_hit_rate:.2%}")
    print(f"Avg keyword score: {avg_keyword_score:.2%}")
    if unsupported_expected_types:
        print(
            "Unsupported expected error types: "
            f"{unsupported_expected_types}. These cases cannot be counted correct "
            "until AnalysisLogResponse.ErrorType and prompts support them."
        )

    # df.to_csv("data/eval_result.csv", index=False, encoding="utf-8-sig")
    # print("Saved result to data/eval_result.csv")


if __name__ == "__main__":
    # 没有RAG的
    asyncio.run(main())
    # 有RAG的
    # asyncio.run(main(True))
