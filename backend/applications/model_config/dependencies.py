# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : dependencies.py
@DateTime: 2026/6/9

ModelConfig 模块依赖注入工厂。

提供模型配置 CRUD 服务的依赖注入工厂函数。
"""
from backend.applications.model_config.services.model_config_crud import ModelConfigCrud


async def get_model_config_crud() -> ModelConfigCrud:
    """获取模型配置 CRUD 服务实例"""
    return ModelConfigCrud()
