# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : model_config_crud.py
@DateTime: 2026/6/9
"""
from typing import List, Optional

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.schemas.model_config_schema import (
    ModelConfigCreate,
    ModelConfigUpdate,
)
from backend.applications.user.models.user_model import User
from backend.core.exceptions import NotFoundException


class ModelConfigCrud(ScaffoldCrud[ModelConfig, ModelConfigCreate, ModelConfigUpdate]):
    def __init__(self):
        super().__init__(model=ModelConfig)

    async def _resolve_user_id(self, current_user: User) -> int:
        if current_user.is_superuser:
            return current_user.id
        admin = await User.get_or_none(username="admin")
        return admin.id if admin else current_user.id

    async def list_by_user(self, user_id: int) -> List[ModelConfig]:
        """获取用户的模型配置列表"""
        return await self.model.filter(user_id=user_id).order_by(
            "-is_default", "-created_time"
        )

    async def get_by_id_and_user(
        self, config_id: str, user_id: int
    ) -> Optional[ModelConfig]:
        """根据 ID 和用户 ID 获取模型配置"""
        return await self.model.get_or_none(id=config_id, user_id=user_id)

    async def get_default_config(self, user_id: int) -> Optional[ModelConfig]:
        """获取用户的默认模型配置"""
        config = await self.model.get_or_none(user_id=user_id, is_default=True)
        if config:
            return config
        return await self.model.filter(user_id=user_id).order_by("created_time").first()

    async def clear_default(
        self, user_id: int, exclude_id: Optional[str] = None
    ) -> None:
        """清除用户的默认配置标记"""
        qs = self.model.filter(user_id=user_id, is_default=True)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        await qs.update(is_default=False)

    async def get_first_other(
        self, user_id: int, exclude_id: str
    ) -> Optional[ModelConfig]:
        """获取用户除指定配置外的第一条配置"""
        return (
            await self.model.filter(user_id=user_id)
            .exclude(id=exclude_id)
            .order_by("created_time")
            .first()
        )

    async def list_configs(self, current_user: User) -> List[ModelConfig]:
        """获取当前用户可见的模型配置列表"""
        user_id = await self._resolve_user_id(current_user)
        return await self.list_by_user(user_id)

    async def create_config(
        self, current_user: User, data: ModelConfigCreate
    ) -> ModelConfig:
        """创建模型配置"""
        if data.is_default:
            await self.clear_default(current_user.id)
        obj_dict = data.create_dict()
        obj_dict["user_id"] = current_user.id
        return await self.create(obj_dict)

    async def get_config(self, config_id: str, current_user: User) -> ModelConfig:
        """获取指定模型配置"""
        config = await self.get_by_id_and_user(config_id, current_user.id)
        if not config:
            raise NotFoundException(message="模型配置不存在")
        return config

    async def update_config(
        self, config_id: str, current_user: User, data: ModelConfigUpdate
    ) -> ModelConfig:
        """更新模型配置"""
        effective_id = data.config_id or config_id
        config = await self.get_config(effective_id, current_user)
        if data.is_default:
            await self.clear_default(current_user.id, exclude_id=effective_id)
        obj_dict = data.model_dump(exclude_unset=True, exclude={"config_id"})
        if obj_dict:
            config = config.update_from_dict(obj_dict)
            await config.save()
        return config

    async def delete_config(self, config_id: str, current_user: User) -> None:
        """删除模型配置"""
        config = await self.get_config(config_id, current_user)
        if config.is_default:
            other = await self.get_first_other(current_user.id, config_id)
            if other:
                other.is_default = True
                await other.save()
        await config.delete()

    async def set_default(self, config_id: str, current_user: User) -> None:
        """设置默认模型配置"""
        config = await self.get_config(config_id, current_user)
        await self.clear_default(current_user.id, exclude_id=config_id)
        config.is_default = True
        await config.save()

    async def get_default(self, current_user: User) -> ModelConfig:
        """获取当前用户的默认模型配置"""
        user_id = await self._resolve_user_id(current_user)
        config = await self.get_default_config(user_id)
        if not config:
            raise NotFoundException(message="没有找到模型配置")
        return config

    async def resolve_for_chat(
        self,
        current_user: User,
        model_config_id: Optional[str] = None,
    ) -> Optional[ModelConfig]:
        """解析聊天场景使用的模型配置"""
        if not current_user.is_superuser:
            admin = await User.get_or_none(username="admin")
            if admin:
                config = await self.get_default_config(admin.id)
                if config:
                    return config

        if model_config_id:
            config = await self.get_by_id_and_user(model_config_id, current_user.id)
            if config:
                return config

        return await self.get_default_config(current_user.id)
