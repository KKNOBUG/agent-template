# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from core.initializations import (
    register_database,
    register_exceptions,
    register_middlewares,
    register_routers,
    init_database_table,
)
from core.responses import SuccessResponse
from applications.ticket_review.lifecycle import start_ticket_review, stop_ticket_review
from applications.code_server_ide.lifecycle import start_code_server_ide, stop_code_server_ide
from applications.ticket_review.services.db1_pool import is_db1_pool_initialized
from applications.ticket_review.services.db2_pool import is_db2_pool_initialized
from applications.code_server_ide.database import is_database_initialized as is_ide_database_initialized

try:
    from configure import PROJECT_CONFIG, ROUTER_SUMMARY, ROUTER_TAGS
except ImportError:
    from core.exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ticket_review_started = False
    code_server_ide_started = False
    app.state.shutting_down = False
    try:
        try:
            await register_database(app)
        except DBConnectionError as e:
            raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {e}")
        await init_database_table(app)
        await start_ticket_review(app)
        ticket_review_started = True
        await start_code_server_ide(app)
        code_server_ide_started = True

        for route in app.routes:
            if isinstance(route, APIRoute):
                ROUTER_SUMMARY[route.path] = route.summary
                ROUTER_TAGS[route.path] = route.tags

        yield
    finally:
        app.state.shutting_down = True
        try:
            if code_server_ide_started:
                await stop_code_server_ide(app)
        finally:
            try:
                if ticket_review_started:
                    await stop_ticket_review(app)
            finally:
                await Tortoise.close_connections()


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    docs_url=PROJECT_CONFIG.APP_DOCS_URL,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=lifespan,
)

register_exceptions(app)
register_middlewares(app)
register_routers(app)


@app.get("/", summary="root", tags=["基础服务"])
async def root():
    return SuccessResponse(message="FastAPI Applications Started Successfully!")


@app.get("/health", summary="健康检查", tags=["基础服务"])
async def health_check():
    worker_error = getattr(app.state, "ticket_review_worker_error", None)
    status = "ok" if not worker_error else "degraded"
    modules = {
        "ticket_review": {
            "started": getattr(app.state, "ticket_review_started", False),
            "db1": is_db1_pool_initialized(),
            "db2": is_db2_pool_initialized(),
            "workerError": worker_error,
        },
        "code_server_ide": {
            "started": getattr(app.state, "code_server_ide_started", False),
            "database": is_ide_database_initialized(),
        },
    }
    return {
        "status": status,
        "version": PROJECT_CONFIG.APP_VERSION,
        "orm": "tortoise-orm",
        "modules": modules,
        # Compatibility fields used by the former ticket-review backend.
        "code": "000000",
        "message": "success",
        "data": {"status": status, "modules": modules},
    }


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app=PROJECT_CONFIG.SERVER_APP,
        host=PROJECT_CONFIG.SERVER_HOST,
        port=PROJECT_CONFIG.SERVER_PORT,
        reload=PROJECT_CONFIG.SERVER_DEBUG,
        reload_delay=PROJECT_CONFIG.SERVER_DELAY,
        reload_excludes=PROJECT_CONFIG.SERVER_RELOAD_EXCLUDES,
        log_config=None,
        log_level=None,
    )

    # ========== 启动命令（在项目根目录下执行，且保证 PYTHONPATH 含所在目录）==========
    # Worker（消费 default + autotest_queue）：
    #   Windows（单线程）：celery -A celery_scheduler.celery_worker worker -Q default,autotest_queue --pool=solo -l INFO
    #   Linux：          celery -A celery_scheduler.celery_worker worker -Q default,autotest_queue -c 4 -l INFO
    # Beat（定时下发 scan_and_dispatch_tasks，必须单独起一个进程）：
    #   celery -A celery_scheduler.celery_worker beat -l INFO
