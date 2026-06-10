# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : model_config_model.py
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
    description = fields.CharField(max_length=255, null=True, description="配置说明")
    model_name = fields.CharField(max_length=64, default="deepseek-chat", description="模型名称")
    temperature = fields.FloatField(default=0.7, description="温度(控制AI回答随机性)")
    max_tokens = fields.IntField(default=4096, description="限制单次回答的最大输出Token数")
    top_p = fields.FloatField(default=0.95, description="Top P(核采样参数)")
    top_k = fields.IntField(default=5, description="Top K(知识库检索条数)")
    max_history_rounds = fields.IntField(default=10, description="保留历史对话轮数")
    score_threshold = fields.FloatField(default=0.0, description="检索相似度阈值(0-1)")
    system_prompt = fields.TextField(default=None, null=True, description="系统提示词，支持{context}占位符")
    is_default = fields.BooleanField(default=True, description="是否默认配置")

    class Meta:
        table = "keenrobot_model_configs"
