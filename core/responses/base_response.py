# -*- coding: utf-8 -*-
from typing import Optional, Any

import orjson
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from enums import Code, Message


class BaseResponse(JSONResponse):
    http_status_code = 200
    code: Code = Code.CODE200
    message: Optional[str] = None
    data: Any = None

    def __init__(
            self,
            http_status_code: Optional[int] = None,
            code: Optional[Code] = None,
            message: Optional[str] = None,
            data: Any = None,
            total: Optional[int] = None, **kwargs
    ):

        if http_status_code and isinstance(http_status_code, int):
            self.http_status_code = http_status_code

        if code and isinstance(code, Code):
            self.code = code.value

        if message and isinstance(message, str):
            status: bool = "错误代码" in message and "错误信息" in message
            self.message = orjson.loads(message)["错误信息"] if status else message
        elif message and isinstance(message, Message):
            self.message = message.value

        if total is not None:
            if isinstance(data, dict):
                data = {**data}
                data.setdefault("total", total)
            else:
                data = {"items": data if data is not None else [], "total": total}
        self.data = data

        resp = dict(
            code=self.code,
            message=self.message,
            data=data,
        )

        super(BaseResponse, self).__init__(
            status_code=self.http_status_code,
            content=jsonable_encoder(resp),
            **kwargs
        )
