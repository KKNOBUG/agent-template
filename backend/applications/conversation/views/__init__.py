# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2026/6/9
"""
from fastapi import APIRouter

from .chat_view import chat
from .history_view import history

chat_router = APIRouter()
history_router = APIRouter()

chat_router.include_router(chat)
history_router.include_router(history)

__all__ = ["chat_router", "history_router"]
