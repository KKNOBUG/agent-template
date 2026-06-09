from typing import Optional, List

from backend.applications.model_config.models.model_config_model import ModelConfig


class ModelConfigRepository:
    @staticmethod
    async def list_by_user(user_id: str) -> List[ModelConfig]:
        return await ModelConfig.filter(user_id=user_id).order_by(
            "-is_default", "-created_at"
        )

    @staticmethod
    async def get_by_id(config_id: str, user_id: str) -> Optional[ModelConfig]:
        return await ModelConfig.get_or_none(id=config_id, user_id=user_id)

    @staticmethod
    async def get_default(user_id: str) -> Optional[ModelConfig]:
        config = await ModelConfig.get_or_none(user_id=user_id, is_default=True)
        if config:
            return config
        return await ModelConfig.filter(user_id=user_id).order_by("created_at").first()

    @staticmethod
    async def clear_default(user_id: str, exclude_id: Optional[str] = None) -> None:
        qs = ModelConfig.filter(user_id=user_id, is_default=True)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        await qs.update(is_default=False)

    @staticmethod
    async def create(user_id: str, **kwargs) -> ModelConfig:
        return await ModelConfig.create(user_id=user_id, **kwargs)

    @staticmethod
    async def delete(config: ModelConfig) -> None:
        await config.delete()

    @staticmethod
    async def get_first_other(user_id: str, exclude_id: str) -> Optional[ModelConfig]:
        return (
            await ModelConfig.filter(user_id=user_id)
            .exclude(id=exclude_id)
            .order_by("created_at")
            .first()
        )
