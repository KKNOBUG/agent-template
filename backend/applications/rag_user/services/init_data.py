# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_data.py
@DateTime: 2026/6/8
"""
from backend.applications.rag_user.models.rag_user_model import RagUser
from backend.configure import LOGGER
from backend.services.rag_security import get_password_hash


async def init_rag_user():
    existing = await RagUser.get_or_none(username="admin")
    if existing:
        existing.hashed_password = get_password_hash("admin")
        existing.is_admin = True
        existing.is_active = True
        await existing.save()
        LOGGER.info("RAG 管理员账号已存在，密码已更新为 admin/admin")
    else:
        await RagUser.create(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin"),
            is_active=True,
            is_admin=True,
        )
        LOGGER.info("RAG 管理员账号创建成功: admin / admin")
