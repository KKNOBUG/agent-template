import uuid

from tortoise import fields, models


class Conversation(models.Model):
    """对话会话"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    user = fields.ForeignKeyField(
        "models.RagUser", related_name="conversations", on_delete=fields.CASCADE
    )
    title = fields.CharField(max_length=200, default="新对话")
    kb_ids = fields.TextField(null=True)
    model_config = fields.ForeignKeyField(
        "models.ModelConfig",
        related_name="conversations",
        null=True,
        on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    messages: fields.ReverseRelation["Message"]

    class Meta:
        table = "conversations"


class Message(models.Model):
    """聊天消息"""

    id = fields.IntField(pk=True)
    conversation = fields.ForeignKeyField(
        "models.Conversation", related_name="messages", on_delete=fields.CASCADE
    )
    role = fields.CharField(max_length=20)
    content = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "messages"
        ordering = ["created_at"]
