# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : rag_auth.py
@DateTime: 2026/6/8
"""
"""RAG 业务认证 - 复用 user 模块用户体系"""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.applications.user.models.user_model import User
from backend.services.rag_security import decode_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Header(default=None),
) -> User:
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")

    # user 模块主键为 BigInt，需转换
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的用户标识")

    user = await User.get_or_none(id=user_id_int)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    return user


DependRagAuth = Depends(get_current_user)
