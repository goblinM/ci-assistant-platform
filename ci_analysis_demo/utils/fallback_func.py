"""
简单规则降级函数
TODO: 后续这里还可以优化
"""


def fallback_rule_analysis(log_text: str) -> dict:
    """执行 ``fallback_rule_analysis`` 对应的 CI 故障诊断。"""
    lower = log_text.lower()

    if "modulenotfounderror" in lower:
        return {
            "error_type": "dependency_missing",
            "summary": "日志显示可能存在 Python 依赖缺失问题。",
            "reason": "日志中出现 ModuleNotFoundError，通常表示运行环境缺少对应 Python 包。",
            "suggestions": [
                "检查 requirements.txt 是否包含缺失依赖",
                "确认 CI 流程是否执行依赖安装步骤"
            ],
            "confidence": "medium",
            "references": []
        }

    if "403" in lower or "forbidden" in lower:
        return {
            "error_type": "repo_auth_failed",
            "summary": "日志显示可能存在仓库认证或权限问题。",
            "reason": "日志中出现 403/Forbidden，通常表示访问私有仓库失败。",
            "suggestions": [
                "检查 CI 环境变量中的 token 是否正确",
                "确认当前账号或 token 是否有私有仓库访问权限"
            ],
            "confidence": "medium",
            "references": []
        }

    return {
        "error_type": "unknown",
        "summary": "AI 分析暂不可用，且规则无法明确判断错误类型。",
        "reason": "当前日志未命中已知规则。",
        "suggestions": [
            "查看完整 CI 日志中的 error、failed、exception 等关键行",
            "人工检查失败阶段和最近代码变更"
        ],
        "confidence": "low",
        "references": []
    }
