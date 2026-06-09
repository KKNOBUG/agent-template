import uuid

from tortoise import fields, models

from backend.applications.base.services.scaffold import ScaffoldModel, MaintainMixin, TimestampMixin, StateModel


class ModelConfig(ScaffoldModel, MaintainMixin, TimestampMixin, StateModel):
    """模型配置"""

    id = fields.CharField(max_length=36, pk=True, default=lambda: str(uuid.uuid4()))
    user = fields.ForeignKeyField(
        "models.User", related_name="model_configs", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=50, default="默认配置")
    model_name = fields.CharField(max_length=50, default="deepseek-chat")
    temperature = fields.FloatField(default=0.7)
    max_tokens = fields.IntField(default=2048)
    top_p = fields.FloatField(default=0.95)
    is_default = fields.BooleanField(default=True)

    class Meta:
        table = "keenrobot_model_configs"
