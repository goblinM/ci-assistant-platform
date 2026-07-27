from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    CONFIG_INVALID = "CONFIG_INVALID"
    AUTH_FAILED = "AUTH_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    WEBHOOK_INVALID = "WEBHOOK_INVALID"
    KNOWLEDGE_INVALID = "KNOWLEDGE_INVALID"
    KNOWLEDGE_INGESTION_FAILED = "KNOWLEDGE_INGESTION_FAILED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_RESPONSE_INVALID = "LLM_RESPONSE_INVALID"
    DIAGNOSIS_FAILED = "DIAGNOSIS_FAILED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class PlatformError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
