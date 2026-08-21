# -*- coding: utf-8 -*-
from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.requests import Request

from core.responses.http_response import SuccessResponse

routers = APIRouter()


@routers.post("/routers", summary="APIRouter-查询总应用路由信息")
async def refresh_router(request: Request):
    app = request.app
    # 获取全部路由数据
    all_router_list = []

    # 更新路由数据
    for route in app.routes:
        if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
            data = {
                'path': route.path_format,
                'method': list(route.methods)[0],
                'summary': route.summary,
                'tags': ','.join(list(route.tags)),
                'description': route.description
            }
            all_router_list.append(data)

    return SuccessResponse(data=all_router_list)
