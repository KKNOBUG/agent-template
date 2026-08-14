# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute

from core.initializations import (
    register_exceptions,
    register_middlewares,
    register_routers,
)

try:
    from configure import PROJECT_CONFIG, ROUTER_SUMMARY, ROUTER_TAGS
except ImportError:
    from core.exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from configure import LOGGER
    from core.initializations import register_database, init_database_table

    # 数据库初始化（Tortoise + Aerich 迁移, MySQL）; 连接失败即快速失败,
    # 避免带着半残状态对外服务
    try:
        await register_database(app)
    except Exception as e:
        raise RuntimeError(f"数据库连接失败, 请检查 MySQL 配置(.env 的 DATABASE_* 项)与连通性: {e}") from e
    await init_database_table(app)

    # 启动巡检（原 dependencies 模块级调用移入此处: 须在数据库就绪后执行）:
    # 基于心跳/Celery 任务状态判定, 仅标记确定性死亡的任务为失败,
    # 仅 Web 重启时不会误伤 Worker 仍在正常处理的任务
    try:
        from applications.jiayueyang.services.rag_service import RagDocumentService
        await RagDocumentService().sweep_stale_documents()
    except Exception as e:
        LOGGER.warning(f"启动僵尸任务巡检失败（不影响服务启动）: {e}")

    # 启动时加载术语库索引（查询改写使用; 依赖文档表, 须在数据库就绪后）
    try:
        from applications.jiayueyang.rag.query_rewriter import load_all_indices
        await load_all_indices()
    except Exception as e:
        LOGGER.warning(f"术语库索引加载失败: {e}")

    for route in app.routes:
        if isinstance(route, APIRoute):
            ROUTER_SUMMARY[route.path] = route.summary
            ROUTER_TAGS[route.path] = route.tags

    yield

    # 关闭数据库连接池（各 gunicorn worker 进程独立持有）
    from tortoise import Tortoise
    await Tortoise.close_connections()


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    # 关闭 FastAPI 默认文档页（其 JS/CSS 走 jsdelivr CDN, 无网环境不可用）;
    # 离线版本由 register_routers -> register_offline_docs 以本地资源重新注册
    docs_url=None,
    redoc_url=None,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=lifespan,
)

register_exceptions(app)
register_middlewares(app)
register_routers(app)


@app.get("/health", summary="健康检查")
async def health_check():
    return {"status": "ok", "version": PROJECT_CONFIG.APP_VERSION, "orm": "tortoise-orm"}


# 前端页面由 nginx（生产, deploy/nginx.conf 托管 web-heroui/dist）或 Vite dev server（开发）提供;
# 前端为 web-heroui（HeroUI v3 版, 兼容无网环境旧版浏览器）;
# 后端只提供 API 与离线接口文档（RAGFlow 式前后端分离, 不托管前端产物）。


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

    # ========== Celery Worker 启动命令（在项目根目录下执行, RAG 文档处理任务由 Worker 异步执行） ==========
    # 注意: Milvus Lite 为单进程嵌入式数据库, 由 Worker 独占访问, Web 的检索/统计/删除
    #       经 Celery RPC 委托 Worker 执行; 线程池保证长转换任务不阻塞 RPC 查询。
    # Windows（线程池）：celery -A celery_scheduler.celery_worker worker -Q default --pool=threads -c 8 -l INFO
    # Linux（进程池）：  celery -A celery_scheduler.celery_worker worker -Q default -c 4 -l INFO
