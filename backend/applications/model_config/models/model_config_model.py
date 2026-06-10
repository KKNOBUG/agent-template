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


class ModelConfig(ScaffoldModel, StateModel, TimestampMixin, MaintainMixin):
    """模型配置"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True, description="配置ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="model_configs",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    name = fields.CharField(max_length=64, default="默认配置", description="配置名称")
    model_name = fields.CharField(max_length=64, default="deepseek-chat", description="模型名称")
    temperature = fields.FloatField(default=0.7, description="温度")
    max_tokens = fields.IntField(default=2048, description="最大Token数")
    top_p = fields.FloatField(default=0.95, description="Top P")
    is_default = fields.BooleanField(default=True, description="是否默认配置")

    class Meta:
        table = "keenrobot_model_configs"
