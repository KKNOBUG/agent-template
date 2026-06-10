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


def encode_knowledge_ids(knowledge_ids: Optional[List[str]]) -> Optional[str]:
    """将知识库 ID 列表编码为数据库存储的 JSON 字符串"""
    if knowledge_ids is None:
        return None
    return json.dumps(knowledge_ids) if knowledge_ids else None


def decode_knowledge_ids(value) -> Optional[List[str]]:
    """将数据库 JSON 字符串解析为知识库 ID 列表"""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


class ConversationBase(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200, description="对话标题")
    knowledge_ids: Optional[List[str]] = Field(default=None, description="关联知识库ID列表")
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")


class ConversationCreate(ConversationBase):
    user_id: int = Field(..., description="用户ID")
    title: str = Field(default="新对话", max_length=200, description="对话标题")

    def create_dict(self):
        obj = self.model_dump(exclude_unset=True)
        if "knowledge_ids" in obj:
            obj["knowledge_ids"] = encode_knowledge_ids(obj.get("knowledge_ids"))
        return obj


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
    knowledge_ids: Optional[List[str]] = Field(default=None, description="关联知识库ID列表")
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")
    created_time: datetime = Field(..., description="创建时间", serialization_alias="created_at")
    updated_time: datetime = Field(..., description="更新时间", serialization_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("knowledge_ids", mode="before")
    @classmethod
    def parse_knowledge_ids(cls, v):
        return decode_knowledge_ids(v)


class ConversationDetail(ConversationOut):
    messages: list["MessageOut"] = Field(default_factory=list, description="消息列表")


class MessageBase(BaseModel):
    role: Optional[str] = Field(default=None, max_length=20, description="消息角色")
    content: Optional[str] = Field(default=None, description="消息内容")


class MessageCreate(MessageBase):
    conversation_id: str = Field(..., description="对话ID")
    role: str = Field(..., max_length=20, description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class MessageUpdate(MessageBase):
    message_id: Optional[int] = Field(default=None, description="消息ID")


class MessageSelect(MessageBase):
    conversation_id: Optional[str] = Field(default=None, description="对话ID")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=10, description="每页数量")
    order: Optional[list] = Field(default=["created_time"], description="排序字段")


class MessageOut(BaseModel):
    id: int = Field(..., description="消息ID")
    role: str = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    created_time: datetime = Field(..., description="创建时间", serialization_alias="created_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: Optional[str] = Field(default=None, description="对话ID")
    knowledge_ids: Optional[List[str]] = Field(default=None, description="关联知识库ID列表")
    model_config_id: Optional[str] = Field(default=None, description="模型配置ID")
