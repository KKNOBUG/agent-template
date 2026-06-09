# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_data
@DateTime: 2026/6/7 12:39
"""
from typing import List

from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER


async def init_database_user():
    """初始化默认用户数据"""
    user_crud = UserCrud()
    user_table = await user_crud.exists()
    if user_table:
        LOGGER.info("[用户]数据表已存在，跳过初始化")
        return
    user_data: List[UserCreate] = [
        UserCreate(
            username="admin",
            password="123456",
            alias="系统管理员",
            email="admin@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            is_active=True,
            is_superuser=True,
        ),
        UserCreate(
            username="guest",
            password="123456",
            alias="访客用户",
            email="guest@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            is_active=True,
            is_superuser=False,
        ),
        UserCreate(
            username="tester",
            password="123456",
            alias="测试用户",
            email="tester@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            is_active=True,
            is_superuser=False,
        )
    ]
    for user_in in user_data:
        try:
            user = await user_crud.create_user(user_in=user_in)
            LOGGER.info(f"创建用户成功: {user.alias} (id: {user.id}, username: {user.username})")
        except Exception as e:
            LOGGER.error(f"创建用户失败: {user_in.alias}, username: {user_in.username}: {e}")
