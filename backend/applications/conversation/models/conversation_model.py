# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : conversation_model.py
@DateTime: 2025/4/28 18:07
"""
from tortoise import fields

from backend.applications.base.services.scaffold import (
    ScaffoldModel,
    StateModel,
    TimestampMixin,
    MaintainMixin,
    unique_identify,
)


class Conversation(ScaffoldModel, StateModel, TimestampMixin, MaintainMixin):
    """对话会话模型"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True, description="对话ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="conversations",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    title = fields.CharField(default="新对话", max_length=255, description="对话标题")
    knowledge_ids = fields.TextField(null=True, description="所属知识库")
    model_config = fields.ForeignKeyField(
        "models.ModelConfig",
        related_name="conversations",
        null=True,
        on_delete=fields.SET_NULL,
        description="所属模型配置",
    )
    messages: fields.ReverseRelation["Message"]

    class Meta:
        table = "keenrobot_conversations"


class Message(ScaffoldModel, StateModel, TimestampMixin, MaintainMixin):
    """聊天消息模型"""
    id = fields.IntField(pk=True, description="消息ID")
    conversation = fields.ForeignKeyField(
        "models.Conversation",
        related_name="messages",
        on_delete=fields.CASCADE,
        description="所属对话",
    )
    role = fields.CharField(max_length=20, description="消息角色")
    content = fields.TextField(description="消息内容")

    class Meta:
        table = "keenrobot_messages"
        ordering = ["created_time"]
