"""
维护错误关键词规则表
TODO：后续继续优化使用数据库去维护
工程化写法：
ERROR_KEYWORD_RULES = [...]
extract_primary_error_keyword(log_text)
优点：
错误类型可扩展
规则集中维护
后续能给每条规则加优先级
后续能统计哪些规则命中最多
方便评测
"""
import re
from dataclasses import dataclass
from typing import Pattern, Callable, Any


@dataclass(frozen=True)
class ErrorKeywordRule:
    """声明兼容层日志故障类型对应的首个正则关键词匹配规则。"""

    error_type: str
    keyword: str
    # re pattern 规则匹配
    pattern: Pattern[str]
    description: str


ERROR_KEYWORD_RULES: list[ErrorKeywordRule] = [
    ErrorKeywordRule(
        error_type="dependency_missing",
        keyword="ModuleNotFoundError",
        pattern=re.compile(r"ModuleNotFoundError:\s+No module named ['\"]?([\w\-\.]+)['\"]?", re.I),
        description="Python dependency missing",
    ),
    ErrorKeywordRule(
        error_type="repo_auth_failed",
        keyword="403",
        pattern=re.compile(r"(403|Forbidden|Unauthorized|401)", re.I),
        description="Repository authentication or permission failed",
    ),
    ErrorKeywordRule(
        error_type="test_failed",
        keyword="AssertionError",
        pattern=re.compile(r"AssertionError|assert\s+.+==.+", re.I),
        description="Unit test assertion failed",
    ),
    ErrorKeywordRule(
        error_type="syntax_error",
        keyword="SyntaxError",
        pattern=re.compile(r"SyntaxError:\s+.+", re.I),
        description="Python syntax error",
    ),
    ErrorKeywordRule(
        error_type="env_config_error",
        keyword="KeyError",
        pattern=re.compile(r"KeyError:\s+['\"]?([\w\-\.]+)['\"]?", re.I),
        description="Environment variable or config missing",
    ),
    ErrorKeywordRule(
        error_type="timeout",
        keyword="timeout",
        pattern=re.compile(r"timeout|timed out|took longer than", re.I),
        description="Job or request timeout",
    ),
]


def extract_error_keywords(log_text: str) -> list[dict]:
    """
    从log text 中解析对应的error keywords
    :param log_text:
    :return:
    """
    matched: list[dict] = []
    for rule in ERROR_KEYWORD_RULES:
        match = rule.pattern.search(log_text)
        if not match:
            continue
        matched.append(
            {
                "error_type": rule.error_type,
                "keyword": rule.keyword,
                "description": rule.description,
                "matched_text": match.group(0),
                "groups": list(match.groups()),
            }
        )
        return matched


def extract_primary_error_keyword(log_text: str) -> dict | None:
    """
    返回主要的error keyword? matched[0]
    :param log_text:
    :return:
    """
    matched = extract_error_keywords(log_text)
    return matched[0] if matched else None
