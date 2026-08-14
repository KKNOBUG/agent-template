# -*- coding: utf-8 -*-
import os
import shutil
import traceback
from typing import Dict, Any

from aerich import Command
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DoesNotExist

from configure import PROJECT_CONFIG, LOGGER
from core.exceptions.http_exceptions import (
    request_validation_exception_handler,
    response_validation_exception_handler,
    http_exception_handler,
    null_point_exception_handler,
    app_exception_handler,
)
from core.middlewares.app_middleware import logging_middleware
from core.middlewares.auth_middleware import auth_middleware
from core.middlewares.request_context_middleware import request_context_middleware

# 离线内置的 swagger-ui / redoc 静态资源目录（随项目分发, 无网环境可用;
# 不放在 web-heroui/dist 内是为了避免被 vite build 的 emptyOutDir 清空）
SWAGGER_VENDOR_DIR = os.path.join(
    PROJECT_CONFIG.PROJECT_ROOT, "static_vendor", "swagger"
)


async def register_database(app: FastAPI) -> None:
    """注册 Tortoise ORM 并执行 Aerich 数据库迁移。

    说明: 本项目的文档表（rag_document）与对话三表（rag_conversation /
    rag_conversation_message / rag_conversation_retrieval）均持久化于 MySQL,
    由 backend_main 的 lifespan 在启动时调用本函数完成连接注册与表结构迁移。
    """
    config: Dict[str, Any] = {
        "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
        "apps": {
            "models": {
                "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                "default_connection": "default"
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }
    register_tortoise(
        app=app,
        config=config,
        generate_schemas=False,
        add_exception_handlers=PROJECT_CONFIG.SERVER_DEBUG,
    )

    # 确保迁移目录存在
    if not os.path.exists(PROJECT_CONFIG.MIGRATION_DIR):
        os.makedirs(PROJECT_CONFIG.MIGRATION_DIR)

    # 初始化Aerich命令
    command = Command(
        app='models',
        tortoise_config=config,
        location=PROJECT_CONFIG.MIGRATION_DIR,
    )

    # 初始化数据库和迁移
    try:
        # 当 safe 设置为 True 时，如果数据库中已经存在 Aerich 所需的迁移表（通常是 aerich 表），init_db 方法不会尝试去重新创建这些表，避免因为表已存在而抛出错误。
        # 当 safe 设置为 False 时，如果数据库中已经存在 Aerich 所需的迁移表，init_db 方法会尝试重新创建这些表，这可能会导致现有表被删除并重新创建，从而丢失表中的数据。
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()

    if not PROJECT_CONFIG.aerich_should_run_on_startup:
        LOGGER.warning(
            "跳过 Aerich 数据迁移指令: \n"
            f"操作系统: {PROJECT_CONFIG.SERVER_SYSTEM}, \n"
            f"调试开关: {PROJECT_CONFIG.SERVER_DEBUG}, \n"
            f"迁移开关: {PROJECT_CONFIG.DATABASE_AUTO_MIGRATION}, \n"
            f"生产环境(Linux操作系统)始终执行迁移指令, 不提供关闭选项; "
            f"开发环境(Windows操作系统)仅当显示打开[DATABASE_AUTO_MIGRATION]时执行迁移指令。"
        )
        return

    # 生成迁移文件
    try:
        await command.migrate(name="auto_migrate")
    except AttributeError as e:
        LOGGER.error(f"无法从数据库中检索模型历史记录, 请检查[migration]与[aerich]表记录是否一致: {e}\n错误回溯: {traceback.format_exc()}")
        if PROJECT_CONFIG.aerich_should_run_on_startup:
            shutil.rmtree(PROJECT_CONFIG.MIGRATION_DIR)
            await command.init_db(safe=True)
        else:
            raise RuntimeError("数据库迁移元数据与本地[migration]不一致, 无法进行迁移, 请手工修复或从备份恢复后再启动应用")

    # 应用迁移
    await command.upgrade(run_in_transaction=True)


# 注册异常处理器
def register_exceptions(app: FastAPI) -> None:
    # 当 FastAPI 在解析和验证请求数据时发现问题，会触发 RequestValidationError 异常
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError,
        handler=request_validation_exception_handler
    )
    # 当 FastAPI 在解析和验证响应数据时发现问题，会触发 ResponseValidationError 异常
    app.add_exception_handler(
        exc_class_or_status_code=ResponseValidationError,
        handler=response_validation_exception_handler
    )
    # 当发生 HTTP 相关的异常时，如 403 禁止访问、404 未找到等，会触发 HTTPException 异常
    app.add_exception_handler(
        exc_class_or_status_code=HTTPException,
        handler=http_exception_handler
    )
    # 当使用 Tortoise ORM 进行数据库查询时，如果查询结果为空，会触发 DoesNotExist 异常
    app.add_exception_handler(
        exc_class_or_status_code=DoesNotExist,
        handler=null_point_exception_handler
    )
    # 当发生未被其他特定异常处理器处理的异常时，会触发此函数
    app.add_exception_handler(IOError, app_exception_handler)
    app.add_exception_handler(OSError, app_exception_handler)
    app.add_exception_handler(KeyError, app_exception_handler)
    app.add_exception_handler(ValueError, app_exception_handler)
    app.add_exception_handler(IndexError, app_exception_handler)
    app.add_exception_handler(TypeError, app_exception_handler)
    app.add_exception_handler(MemoryError, app_exception_handler)
    app.add_exception_handler(ImportError, app_exception_handler)
    app.add_exception_handler(TimeoutError, app_exception_handler)
    app.add_exception_handler(RuntimeError, app_exception_handler)
    app.add_exception_handler(AttributeError, app_exception_handler)
    app.add_exception_handler(FileExistsError, app_exception_handler)
    app.add_exception_handler(FileNotFoundError, app_exception_handler)
    app.add_exception_handler(NotADirectoryError, app_exception_handler)
    app.add_exception_handler(DoesNotExist, app_exception_handler)
    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=app_exception_handler
    )


def register_middlewares(app: FastAPI):
    # 注册 CORS 中间件，CORS（跨域资源共享）中间件用于处理跨域请求，允许不同域名的客户端访问服务器资源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=PROJECT_CONFIG.CORS_ORIGINS,
        allow_credentials=PROJECT_CONFIG.CORS_ALLOW_CREDENTIALS,
        allow_methods=PROJECT_CONFIG.CORS_ALLOW_METHODS,
        allow_headers=PROJECT_CONFIG.CORS_ALLOW_HEADERS,
        expose_headers=PROJECT_CONFIG.CORS_EXPOSE_METHODS,
        max_age=PROJECT_CONFIG.CORS_MAX_AGE,
    )
    # 注册 HTTP 请求中间件
    app.middleware('http')(auth_middleware)
    # 先做认证拦截，再做审计日志记录
    app.middleware('http')(logging_middleware)
    # 后做日志追溯链
    app.middleware('http')(request_context_middleware)
    # 响应压缩（最外层, 压缩最终响应体）: markdown/chunks 等大 JSON 响应可压缩 5~8 倍,
    # 显著加快大文档内容传输（生产 nginx 亦有 gzip, 此处补齐开发/直连场景）。
    # minimum_size 与 nginx gzip_min_length 对齐, 过小的响应不压缩。
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # 离线 vendor 资源强制再验证: StaticFiles 不带 Cache-Control, 浏览器按启发式
    # 缓存长期使用旧副本——vendor 更新(如剥离 sourceMappingURL 注释)后, 客户端
    # 仍用旧 CSS, DevTools 继续按旧注释请求 .map 报 404。no-cache 每次再验证,
    # ETag 未变即 304, 开销可忽略, 保证 vendor 更新即时生效。
    @app.middleware("http")
    async def swagger_assets_no_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/swagger-assets/"):
            response.headers["Cache-Control"] = "no-cache"
        return response


def register_offline_docs(app: FastAPI) -> None:
    """注册完全离线的接口文档（Swagger UI / ReDoc）。

    FastAPI 默认的 /docs 与 /redoc 从 jsdelivr CDN 加载 JS/CSS, 无网环境不可用;
    这里关闭默认文档页（backend_main 以 docs_url=None / redoc_url=None 创建应用）,
    改用本地内置资源（static_vendor/swagger/）渲染文档页面。
    """
    if not os.path.isdir(SWAGGER_VENDOR_DIR):
        LOGGER.warning(f"离线文档资源目录不存在, 接口文档不可用: {SWAGGER_VENDOR_DIR}")
        return

    # 本地 swagger-ui / redoc 静态资源
    app.mount(
        "/swagger-assets",
        StaticFiles(directory=SWAGGER_VENDOR_DIR),
        name="swagger-assets",
    )

    docs_url = PROJECT_CONFIG.APP_DOCS_URL
    oauth2_redirect_url = f"{docs_url}/oauth2-redirect"

    @app.get(docs_url, include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=oauth2_redirect_url,
            swagger_js_url="/swagger-assets/swagger-ui-bundle.js",
            swagger_css_url="/swagger-assets/swagger-ui.css",
            swagger_favicon_url="/swagger-assets/favicon.png",
        )

    @app.get(oauth2_redirect_url, include_in_schema=False)
    async def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()

    @app.get(PROJECT_CONFIG.APP_REDOC_URL, include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
            title=f"{app.title} - ReDoc",
            redoc_js_url="/swagger-assets/redoc.standalone.js",
            redoc_favicon_url="/swagger-assets/favicon.png",
            # 离线环境: 关闭模板默认的 Google Fonts 外链（Montserrat/Roboto）,
            # 回退系统字体栈, 避免无网时发起失败的外网请求
            with_google_fonts=False,
        )


def register_routers(app: FastAPI) -> None:
    # 离线接口文档（Swagger UI / ReDoc 本地资源; 前端产物改由 nginx 托管, 后端不再挂载）
    register_offline_docs(app)

    # 导入路由蓝图
    from applications.jiayueyang.views import rag_public_router, rag_secure_router

    # 挂载路由蓝图
    # 公开路由: 健康检查类接口, 无需鉴权
    app.include_router(router=rag_public_router, prefix="/api", tags=["RAG-文档智能解析与问答"])
    # 业务路由: zsj 模板约定由挂载处统一施加 dependencies=[DependAuth] 鉴权;
    # 本项目当前未引入用户体系（无 User 模型 / 无 Token 签发入口, auth_middleware
    # 相应将 /api/* 列入白名单）, 业务路由暂按公开方式挂载;
    # 引入用户体系后, 取消下方 dependencies 注释并同步移除 auth_middleware 的 /api/* 白名单即可启用鉴权。
    # from services import DependAuth
    app.include_router(
        router=rag_secure_router,
        prefix="/api",
        tags=["RAG-文档智能解析与问答"],
        # dependencies=[DependAuth],  # 鉴权开关: 用户体系与 Token 签发入口就绪后启用
    )
