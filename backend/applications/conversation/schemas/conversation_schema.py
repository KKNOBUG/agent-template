# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : conversation_schema.py
@DateTime: 2026/6/10
"""
import json
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.enums.chat_session_enum import ChatMessageRole


def normalize_knowledge_base_ids(value) -> Optional[List[str]]:
    """统一知识库 ID 列表（兼容 JSONField 与历史 LONGTEXT JSON 字符串）"""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


class ConversationBase(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255, description="对话标题")
    knowledge_base_ids: Optional[List[str]] = Field(
        default=None, description="关联知识库ID列表"
    )
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")


class ConversationCreate(ConversationBase):
    user_id: int = Field(..., description="用户ID")
    title: str = Field(default="新对话", max_length=255, description="对话标题")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class ConversationUpdate(ConversationBase):
    conversation_id: Optional[str] = Field(default=None, description="对话ID")


class ConversationSelect(ConversationBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=["-updated_time"], description="排序字段")


class ConversationOut(BaseModel):
    id: str = Field(..., description="对话ID")
    user_id: int = Field(..., description="用户ID")
    title: str = Field(..., description="对话标题")
    knowledge_base_ids: Optional[List[str]] = Field(
        default=None, description="关联知识库ID列表"
    )
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")
    created_time: datetime = Field(..., description="创建时间", serialization_alias="created_at")
    updated_time: datetime = Field(..., description="更新时间", serialization_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("knowledge_base_ids", mode="before")
    @classmethod
    def parse_knowledge_base_ids(cls, v):
        return normalize_knowledge_base_ids(v)


class ConversationDetail(ConversationOut):
    messages: list["MessageOut"] = Field(default_factory=list, description="消息列表")


class MessageBase(BaseModel):
    role: Optional[ChatMessageRole] = Field(default=None, description="消息角色")
    content: Optional[str] = Field(default=None, description="消息内容")


class MessageCreate(MessageBase):
    conversation_id: str = Field(..., description="对话ID")
    role: ChatMessageRole = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")

    def create_dict(self):
        obj = self.model_dump(exclude_unset=True)
        if isinstance(obj.get("role"), ChatMessageRole):
            obj["role"] = obj["role"].value
        return obj


class MessageUpdate(MessageBase):
    message_id: Optional[int] = Field(default=None, description="消息ID")


class MessageSelect(MessageBase):
    conversation_id: Optional[str] = Field(default=None, description="对话ID")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=10, description="每页数量")
    order: Optional[list] = Field(default=["created_time"], description="排序字段")


class MessageOut(BaseModel):
    id: int = Field(..., description="消息ID")
    role: ChatMessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    created_time: datetime = Field(..., description="创建时间", serialization_alias="created_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: Optional[str] = Field(default=None, description="对话ID")
    knowledge_base_ids: Optional[List[str]] = Field(
        default=None,
        description="关联知识库ID列表；传 [] 表示清空绑定，不传则沿用会话已存值",
    )
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")
