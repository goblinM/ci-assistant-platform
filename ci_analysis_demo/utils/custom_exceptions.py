"""
自定义异常
"""


class LLMServiceError(Exception):
    pass


class LLMTimeoutError(LLMServiceError):
    pass


class LLMResponseFormatError(LLMServiceError):
    pass
