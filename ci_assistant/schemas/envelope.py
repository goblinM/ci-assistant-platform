from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class Envelope(BaseModel, Generic[DataT]):
    request_id: str
    data: DataT | None = None
    error: ErrorBody | None = None

