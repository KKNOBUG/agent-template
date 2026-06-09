# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2026/6/9
"""
from fastapi import APIRouter

from .model_config_view import model_config

model_router = APIRouter()
model_router.include_router(model_config)

__all__ = ["model_router"]
