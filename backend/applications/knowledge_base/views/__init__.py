# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2026/6/9
"""
from fastapi import APIRouter

from .knowledge_base_view import knowledge_base

kb_router = APIRouter()
kb_router.include_router(knowledge_base)

__all__ = ["kb_router"]
