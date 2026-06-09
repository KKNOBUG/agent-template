# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_data.py
@DateTime: 2026/6/8
"""
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.rag_user.models.rag_user_model import RagUser
from backend.configure import LOGGER


async def init_model_configs():
    admin = await RagUser.get_or_none(username="admin")
    if not admin:
        LOGGER.warning("跳过模型配置初始化: RAG 管理员账号不存在")
        return

    if await ModelConfig.filter(user_id=admin.id).exists():
        LOGGER.info("模型配置已存在，跳过初始化")
        return

    await ModelConfig.create(
        user_id=admin.id,
        name="默认配置",
        model_name="deepseek-chat",
        temperature=0.7,
        max_tokens=2048,
        top_p=0.95,
        is_default=True,
    )
    LOGGER.info("默认模型配置初始化完成")
