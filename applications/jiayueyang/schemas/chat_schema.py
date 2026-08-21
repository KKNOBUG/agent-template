# -*- coding: utf-8 -*-
"""对话历史接口的请求模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """新建会话请求"""
    title: Optional[str] = Field(default="新对话", max_length=255, description="会话标题（缺省为 新对话, 首次提问后自动更新）")


class ConversationRename(BaseModel):
    """重命名会话请求"""
    title: str = Field(..., min_length=1, max_length=255, description="新的会话标题")


class ConversationPin(BaseModel):
    """置顶/取消置顶会话请求"""
    pinned: bool = Field(..., description="是否置顶")
