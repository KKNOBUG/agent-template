# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/4/28 18:07
"""
from backend.applications.knowledge_base.services.knowledge_base_crud import (
    DocumentChunkCrud,
    DocumentCrud,
    KnowledgeBaseCrud,
)

__all__ = ["KnowledgeBaseCrud", "DocumentCrud", "DocumentChunkCrud"]
