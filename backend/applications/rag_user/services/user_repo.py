from typing import Optional

from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.model_config.models.model_config_model import ModelConfig


class UserRepository:
    @staticmethod
    async def get_by_id(user_id: str) -> Optional[User]:
        return await User.get_or_none(id=user_id)

    @staticmethod
    async def get_by_username(username: str) -> Optional[User]:
        return await User.get_or_none(username=username)

    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        return await User.get_or_none(email=email)

    @staticmethod
    async def create(username: str, email: str, hashed_password: str) -> User:
        return await User.create(
            username=username,
            email=email,
            hashed_password=hashed_password,
        )

    @staticmethod
    async def get_admin() -> Optional[User]:
        return await User.get_or_none(username="admin")

    @staticmethod
    async def copy_model_configs(from_user: User, to_user: User) -> int:
        configs = await ModelConfig.filter(user_id=from_user.id).all()
        for config in configs:
            await ModelConfig.create(
                user_id=to_user.id,
                name=config.name,
                model_name=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                is_default=config.is_default,
            )
        return len(configs)
