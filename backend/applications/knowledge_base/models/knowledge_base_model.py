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


class KnowledgeBase(ScaffoldModel, StateModel, TimestampMixin, MaintainMixin):
    """知识库模型"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True, description="知识库ID")
    name = fields.CharField(max_length=128, description="知识库名称")
    description = fields.TextField(null=True, description="知识库描述")
    owner = fields.ForeignKeyField(
        "models.User",
        related_name="knowledge_bases",
        on_delete=fields.CASCADE,
        description="所属用户",
    )
    is_public = fields.BooleanField(default=False, description="是否公开")

    documents: fields.ReverseRelation["Document"]

    class Meta:
        table = "keenrobot_knowledge_bases"


class Document(ScaffoldModel, TimestampMixin):
    """文档模型"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True, description="文档ID")
    kb = fields.ForeignKeyField(
        "models.KnowledgeBase",
        related_name="documents",
        on_delete=fields.CASCADE,
        description="所属知识库",
    )
    filename = fields.CharField(max_length=255, description="文件名")
    file_path = fields.CharField(max_length=512, description="文件路径")
    file_size = fields.IntField(description="文件大小(字节)")
    chunk_count = fields.IntField(default=0, description="分块数量")
    status = fields.CharField(max_length=32, default="processing", description="处理状态")
    error_msg = fields.TextField(null=True, description="错误信息")

    chunks: fields.ReverseRelation["DocumentChunk"]

    class Meta:
        table = "keenrobot_documents"


class DocumentChunk(ScaffoldModel, TimestampMixin):
    """文档分块模型"""
    id = fields.CharField(default=unique_identify, max_length=64, pk=True, description="分块ID")
    doc = fields.ForeignKeyField(
        "models.Document",
        related_name="chunks",
        on_delete=fields.CASCADE,
        description="所属文档",
    )
    content = fields.TextField(description="分块内容")
    chunk_index = fields.IntField(description="分块序号")
    chroma_id = fields.CharField(max_length=128, null=True, description="Chroma向量ID")

    class Meta:
        table = "keenrobot_document_chunks"
