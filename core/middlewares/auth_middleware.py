# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import Iterable, Optional

import jwt
from fastapi import Request

from configure import LOGGER, PROJECT_CONFIG
from core.responses import UnauthorizedResponse


def _normalize_path(path: str) -> str:
    """对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。"""
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def _rule_matches(rule: str, request_method: str, request_path: str) -> bool:
    """
    白名单规则格式:
      - "METHOD /path" (精确匹配)
      - "METHOD /path/*" (前缀匹配)
      - METHOD 为 "*" 时匹配任意请求方法
    """
    rule = rule.strip()
    if not rule:
        return False

    parts = rule.split(" ", 1)
    if len(parts) != 2:
        return False

    rule_method, rule_path_pattern = parts
    rule_method = rule_method.upper()

    if rule_method != "*" and rule_method != request_method:
        return False

    rule_path_pattern = _normalize_path(rule_path_pattern)

    # 前缀匹配: /static/* => /static/<任意子路径>
    if rule_path_pattern.endswith("/*"):
        base = rule_path_pattern[: -len("/*")]
        base = _normalize_path(base)
        return request_path == base or request_path.startswith(base + "/")

    # 精确匹配
    return request_path == rule_path_pattern


def _is_whitelisted(whitelist: Iterable[str], request_method: str, request_path: str) -> bool:
    for rule in whitelist:
        if _rule_matches(rule, request_method=request_method, request_path=request_path):
            return True
    return False


async def auth_middleware(request: Request, call_next):
    """JWT 鉴权中间件: 白名单路由直接放行, 其余路由校验请求头中的 Token。

    说明: 本项目未启用用户体系, Token 仅做签名与有效期校验（jwt.decode）,
    不做用户查库与吊销检查; RAG 业务路由 (/api/*) 默认公开访问。
    """
    request_method = request.method.upper()
    request_path = _normalize_path(request.url.path)

    # 允许CORS前置请求
    if request_method == "OPTIONS":
        return await call_next(request)

    whitelist = [
        # 健康检查
        "GET /health",

        # openapi/docs（含离线文档页的 oauth2 回调）
        f"GET {PROJECT_CONFIG.APP_DOCS_URL}",
        f"GET {PROJECT_CONFIG.APP_DOCS_URL}/oauth2-redirect",
        f"GET {PROJECT_CONFIG.APP_REDOC_URL}",
        f"GET {PROJECT_CONFIG.APP_OPENAPI_URL}",

        # 离线 swagger-ui 资源（前端静态资源由 nginx 托管, 不经过后端）
        "* /swagger-assets/*",

        # RAG 业务路由默认公开
        "* /api/*",
    ]

    if _is_whitelisted(whitelist=whitelist, request_method=request_method, request_path=request_path):
        return await call_next(request)

    token = request.headers.get("token")
    if not token:
        return UnauthorizedResponse(message="请求服务鉴权失败, 请携带有效 Token 进行访问")

    try:
        decode_data: Optional[dict] = jwt.decode(
            jwt=token,
            key=PROJECT_CONFIG.AUTH_SECRET_KEY,
            algorithms=[PROJECT_CONFIG.AUTH_JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        return UnauthorizedResponse(
            message="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问"
        )
    except jwt.DecodeError:
        return UnauthorizedResponse(message="请求服务鉴权失败, 请携带有效 Token 进行访问")
    except jwt.InvalidTokenError:
        return UnauthorizedResponse(message="请求服务鉴权失败, Token 无效, 请重新登录")
    except Exception as exc:
        LOGGER.error(
            f"鉴权中间件异常: {exc}\n{traceback.format_exc()}"
        )
        return UnauthorizedResponse(message="请求服务鉴权失败, 服务暂时不可用, 请稍后重试")
    return await call_next(request)
