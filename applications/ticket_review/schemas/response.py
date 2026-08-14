from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: str
    message: str
    data: Any = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code="000000", message=message, data=data)

    @classmethod
    def error(cls, message: str, data: Any = None, code: str = "E000000") -> "ApiResponse":
        return cls(code=code, message=message, data=data)

    def to_json_response(self) -> JSONResponse:
        return JSONResponse(status_code=200, content=self.model_dump())
