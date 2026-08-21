# -*- coding: utf-8 -*-
from fastapi import FastAPI

from core.initializations import (
    application_health,
    application_lifespan,
    register_exceptions,
    register_middlewares,
    register_routers,
)
from core.responses import SuccessResponse

try:
    from configure import PROJECT_CONFIG
except ImportError:
    from core.exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败，请检查 configure.project_config.py 文件")


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    docs_url=PROJECT_CONFIG.APP_DOCS_URL,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=application_lifespan,
)

register_exceptions(app)
register_middlewares(app)
register_routers(app)


@app.get("/", summary="root", tags=["基础服务"])
async def root():
    return SuccessResponse(message="FastAPI Applications Started Successfully!")


@app.get("/health", summary="健康检查", tags=["基础服务"])
async def health_check():
    health = application_health(app)
    return SuccessResponse(
        data={
            "status": health["status"],
            "version": PROJECT_CONFIG.APP_VERSION,
            "orm": "tortoise-orm",
            "modules": health["modules"],
        }
    )


if __name__ == "__main__":
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

    # Celery 进程仍按主项目原有方式单独启动：
    # Windows: celery -A celery_scheduler.celery_worker worker -Q default,autotest_queue --pool=solo -l INFO
    # Linux:   celery -A celery_scheduler.celery_worker worker -Q default,autotest_queue -c 4 -l INFO
    # Beat:    celery -A celery_scheduler.celery_worker beat -l INFO
