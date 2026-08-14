# -*- coding: utf-8 -*-
"""认证依赖（DependAuth）。

移植自 zsj 模板 services/dependency.py, 并做适配:
- zsj 版: JWT 解码 → 查询 User 模型 → token_version 吊销检查 → 返回 User 实例
- 本项目未引入用户体系（无 User 模型 / 无登录签发入口）, 适配版仅做
  JWT 签名与有效期校验, 返回解码后的载荷; CTX_USER_ID 取载荷中的
  user_id 字段（缺省为 0）。

后续引入用户体系后, 应将本文件恢复为 zsj 的查库版本, 并在
core/initializations/app_initialization.py 的路由挂载处启用 DependAuth。
"""
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, Header, HTTPException

from configure import PROJECT_CONFIG
from services.ctx import CTX_USER_ID


class AuthControl:
    @classmethod
    async def is_authed(cls, token: str = Header(..., description="token验证")) -> Optional[Dict[str, Any]]:
        try:
            decode_data = jwt.decode(
                jwt=token,
                key=PROJECT_CONFIG.AUTH_SECRET_KEY,
                algorithms=[PROJECT_CONFIG.AUTH_JWT_ALGORITHM],
            )
            CTX_USER_ID.set(int(decode_data.get("user_id") or 0))
            return decode_data
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问",
            )
        except jwt.DecodeError:
            raise HTTPException(
                status_code=401,
                detail="请求服务鉴权失败, 请携带有效 Token 进行访问",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="请求服务鉴权失败, Token 无效, 请重新登录",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{repr(e)}")


DependAuth = Depends(AuthControl.is_authed)
