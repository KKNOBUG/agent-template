from datetime import timedelta

from fastapi import HTTPException, status

from backend.configure import PROJECT_CONFIG
from backend.services.rag_security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.rag_user.services.user_repo import UserRepository
from backend.applications.rag_user.schemas.rag_user_schema import UserCreate, UserLogin, Token


class AuthService:
    @staticmethod
    async def register(user_data: UserCreate) -> User:
        if await UserRepository.get_by_username(user_data.username):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
        if await UserRepository.get_by_email(user_data.email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

        user = await UserRepository.create(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
        )

        admin = await UserRepository.get_admin()
        if admin:
            try:
                await UserRepository.copy_model_configs(admin, user)
            except Exception as e:
                print(f"[register] 复制配置失败: {e}")

        return user

    @staticmethod
    async def login(login_data: UserLogin) -> Token:
        user = await UserRepository.get_by_username(login_data.username)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

        token = create_access_token(
            data={"sub": user.id},
            expires_delta=timedelta(minutes=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return Token(
            access_token=token,
            token_type="bearer",
            expires_in=PROJECT_CONFIG.AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
