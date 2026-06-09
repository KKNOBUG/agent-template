from typing import List, Optional

from fastapi import HTTPException, status

from backend.applications.user.models.user_model import User
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.services.model_config_repo import ModelConfigRepository
from backend.applications.model_config.schemas.model_config_schema import ModelConfigCreate


class ModelConfigService:
    @staticmethod
    async def _resolve_user_id(current_user: User) -> int:
        if current_user.is_superuser:
            return current_user.id
        admin = await User.get_or_none(username="admin")
        return admin.id if admin else current_user.id

    @classmethod
    async def list_configs(cls, current_user: User) -> List[ModelConfig]:
        user_id = await cls._resolve_user_id(current_user)
        return await ModelConfigRepository.list_by_user(user_id)

    @classmethod
    async def create_config(
        cls, current_user: User, data: ModelConfigCreate
    ) -> ModelConfig:
        if data.is_default:
            await ModelConfigRepository.clear_default(current_user.id)
        return await ModelConfigRepository.create(
            user_id=current_user.id,
            name=data.name,
            model_name=data.model_name,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            top_p=data.top_p,
            is_default=data.is_default,
        )

    @staticmethod
    async def get_config(config_id: str, current_user: User) -> ModelConfig:
        config = await ModelConfigRepository.get_by_id(config_id, current_user.id)
        if not config:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="模型配置不存在")
        return config

    @staticmethod
    async def update_config(
        config_id: str, current_user: User, data: ModelConfigCreate
    ) -> ModelConfig:
        config = await ModelConfigService.get_config(config_id, current_user)
        if data.is_default:
            await ModelConfigRepository.clear_default(current_user.id, exclude_id=config_id)
        config.name = data.name
        config.model_name = data.model_name
        config.temperature = data.temperature
        config.max_tokens = data.max_tokens
        config.top_p = data.top_p
        config.is_default = data.is_default
        await config.save()
        return config

    @staticmethod
    async def delete_config(config_id: str, current_user: User) -> None:
        config = await ModelConfigService.get_config(config_id, current_user)
        if config.is_default:
            other = await ModelConfigRepository.get_first_other(
                current_user.id, config_id
            )
            if other:
                other.is_default = True
                await other.save()
        await ModelConfigRepository.delete(config)

    @staticmethod
    async def set_default(config_id: str, current_user: User) -> None:
        config = await ModelConfigService.get_config(config_id, current_user)
        await ModelConfigRepository.clear_default(current_user.id, exclude_id=config_id)
        config.is_default = True
        await config.save()

    @classmethod
    async def get_default(cls, current_user: User) -> ModelConfig:
        user_id = await cls._resolve_user_id(current_user)
        config = await ModelConfigRepository.get_default(user_id)
        if not config:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="没有找到模型配置")
        return config

    @classmethod
    async def resolve_for_chat(
        cls,
        current_user: User,
        model_config_id: Optional[str] = None,
    ) -> Optional[ModelConfig]:
        if not current_user.is_superuser:
            admin = await User.get_or_none(username="admin")
            if admin:
                config = await ModelConfigRepository.get_default(admin.id)
                if config:
                    return config

        if model_config_id:
            config = await ModelConfigRepository.get_by_id(
                model_config_id, current_user.id
            )
            if config:
                return config

        return await ModelConfigRepository.get_default(current_user.id)
