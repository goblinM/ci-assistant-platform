from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ErrorBody(BaseModel):
    """定义 API Envelope 中不泄漏内部异常的稳定错误结构。"""

    code: str
    message: str
    details: dict[str, Any] | None = None


class Envelope(BaseModel, Generic[DataT]):
    """统一封装请求 ID、成功数据或错误信息，二者按响应语义互斥。"""

    request_id: str
    data: DataT | None = None
    error: ErrorBody | None = None
