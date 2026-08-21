# -*- coding: utf-8 -*-
from typing import Optional, Union, List, Any, Dict

from core.responses import BaseResponse
from enums import Code, Message

DataType = Optional[Union[int, str, List, Dict[str, Any]]]


class SuccessResponse(BaseResponse):
    code = Code.CODE200
    message = Message.MESSAGE200
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(SuccessResponse, self).__init__(message=message, data=data, total=total)


class FailureResponse(BaseResponse):
    code = Code.CODE999
    message = Message.MESSAGE999
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FailureResponse, self).__init__(message=message, data=data, total=total)


class BadReqResponse(BaseResponse):
    code = Code.CODE400
    message = "请求失败"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(BadReqResponse, self).__init__(message=message, data=data, total=total)


class SyntaxErrorResponse(BaseResponse):
    code = Code.CODE999
    message = "语法错误"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(SyntaxErrorResponse, self).__init__(message=message, data=data, total=total)


class ParameterResponse(BaseResponse):
    code = Code.CODE400
    message = Message.MESSAGE400
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(ParameterResponse, self).__init__(message=message, data=data, total=total)


class FileExtensionResponse(BaseResponse):
    code = Code.CODE400
    message = "文件扩展名不符合规范"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FileExtensionResponse, self).__init__(message=message, data=data, total=total)


class FileTooManyResponse(BaseResponse):
    code = Code.CODE400
    message = "文件数量过多或体积过大"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(FileTooManyResponse, self).__init__(message=message, data=data, total=total)


class DataBaseStorageResponse(BaseResponse):
    code = Code.CODE400
    message = "数据库存储异常"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(DataBaseStorageResponse, self).__init__(message=message, data=data, total=total)


class DataAlreadyExistsResponse(BaseResponse):
    code = Code.CODE400
    message = "数据或文件已存在"
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(DataAlreadyExistsResponse, self).__init__(message=message, data=data, total=total)


class UnauthorizedResponse(BaseResponse):
    code = Code.CODE401
    message = Message.MESSAGE401
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(UnauthorizedResponse, self).__init__(message=message, data=data, total=total)


class ForbiddenResponse(BaseResponse):
    code = Code.CODE403
    message = Message.MESSAGE403
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(ForbiddenResponse, self).__init__(message=message, data=data, total=total)


class NotFoundResponse(BaseResponse):
    code = Code.CODE404
    message = Message.MESSAGE404
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(NotFoundResponse, self).__init__(message=message, data=data, total=total)


class MethodNotAllowedResponse(BaseResponse):
    code = Code.CODE405
    message = Message.MESSAGE405
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(MethodNotAllowedResponse, self).__init__(message=message, data=data, total=total)


class RequestTimeoutResponse(BaseResponse):
    code = Code.CODE408
    message = Message.MESSAGE408
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(RequestTimeoutResponse, self).__init__(message=message, data=data, total=total)


class LimiterResponse(BaseResponse):
    code = Code.CODE429
    message = Message.MESSAGE429
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(LimiterResponse, self).__init__(message=message, data=data, total=total)


class InternalErrorResponse(BaseResponse):
    code = Code.CODE500
    message = Message.MESSAGE500
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(InternalErrorResponse, self).__init__(message=message, data=data, total=total)


class BadGatewayResponse(BaseResponse):
    code = Code.CODE502
    message = Message.MESSAGE502
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(BadGatewayResponse, self).__init__(message=message, data=data, total=total)


class GatewayTimeoutResponse(BaseResponse):
    code = Code.CODE504
    message = Message.MESSAGE504
    data = {}
    total = None

    def __init__(self, message: Optional[str] = None, data: DataType = None, total: Optional[int] = None):
        super(GatewayTimeoutResponse, self).__init__(message=message, data=data, total=total)
