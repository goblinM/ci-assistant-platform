"""
自定义异常
"""


class LLMServiceError(Exception):
    """表示兼容层模型调用或结果处理失败的基础异常。"""

    pass


class LLMTimeoutError(LLMServiceError):
    """表示兼容层模型请求在配置的时间限制内未完成。"""

    pass


class LLMResponseFormatError(LLMServiceError):
    """表示兼容层模型响应无法解析为约定的结构化诊断。"""

    pass
