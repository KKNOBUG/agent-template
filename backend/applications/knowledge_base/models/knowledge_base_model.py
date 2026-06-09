import uuid

from tortoise import fields, models


class KnowledgeBase(models.Model):
    """知识库"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    owner = fields.ForeignKeyField(
        "models.RagUser", related_name="knowledge_bases", on_delete=fields.CASCADE
    )
    is_public = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    documents: fields.ReverseRelation["Document"]

    class Meta:
        table = "knowledge_bases"


class Document(models.Model):
    """文档"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    kb = fields.ForeignKeyField(
        "models.KnowledgeBase", related_name="documents", on_delete=fields.CASCADE
    )
    filename = fields.CharField(max_length=255)
    file_path = fields.CharField(max_length=500)
    file_size = fields.IntField()
    chunk_count = fields.IntField(default=0)
    status = fields.CharField(max_length=20, default="processing")
    error_msg = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    chunks: fields.ReverseRelation["DocumentChunk"]

    class Meta:
        table = "documents"


class DocumentChunk(models.Model):
    """文档分块"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    doc = fields.ForeignKeyField(
        "models.Document", related_name="chunks", on_delete=fields.CASCADE
    )
    content = fields.TextField()
    chunk_index = fields.IntField()
    chroma_id = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "document_chunks"
