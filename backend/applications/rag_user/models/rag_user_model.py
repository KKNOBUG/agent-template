import uuid

from tortoise import fields, models


class RagUser(models.Model):
    """RAG 业务用户（与 template krun_user 隔离）"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    username = fields.CharField(max_length=50, unique=True, index=True)
    email = fields.CharField(max_length=100, unique=True, index=True)
    hashed_password = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    conversations: fields.ReverseRelation["Conversation"]
    knowledge_bases: fields.ReverseRelation["KnowledgeBase"]
    model_configs: fields.ReverseRelation["ModelConfig"]

    class Meta:
        table = "users"


User = RagUser
