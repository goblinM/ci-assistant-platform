"""将原始 CI 日志清洗成适合检索的短 query。"""
import re

from ..tools.rules import extract_primary_error_keyword


ERROR_PATTERNS = [
    r"ModuleNotFoundError:.*",
    r"ImportError:.*",
    r"AssertionError:.*",
    r"SyntaxError:.*",
    r"KeyError:.*",
    r".*403.*Forbidden.*",
    r".*401.*Unauthorized.*",
    r".*timed out.*",
    r".*took longer than.*",
    r".*failed.*",
    r".*ERROR.*",
]


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TIMESTAMP_RE = re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}[T\s][\d:.+,Z-]+\s*)")


def extract_query_from_log(
        log_text: str,
        max_lines: int = 12,
        max_chars: int = 2000,
) -> str:
    """提取去重后的关键错误行，限制长度，避免完整日志直接 embedding。"""
    cleaned_text = ANSI_ESCAPE_RE.sub("", log_text)
    lines = cleaned_text.splitlines()
    matched_lines: list[str] = []

    for line in lines:
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, line, re.I):
                normalized_line = TIMESTAMP_RE.sub("", line).strip()
                if normalized_line and normalized_line not in matched_lines:
                    matched_lines.append(normalized_line)
                break

    selected_lines = matched_lines[:max_lines] if matched_lines else [
        line.strip() for line in lines[-max_lines:] if line.strip()
    ]
    query = "\n".join(selected_lines)
    return query[:max_chars]


def build_rag_filters(
        log_text: str,
        primary_error: dict | None = None,
) -> dict[str, str]:
    """把规则识别结果转换为知识库 metadata 过滤条件。"""
    primary_error = primary_error or extract_primary_error_keyword(log_text)
    if not primary_error:
        return {}

    error_type = primary_error.get("error_type")
    return {"error_type": str(error_type)} if error_type else {}
