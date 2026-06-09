# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_admin.py
@DateTime: 2025/4/28 18:07
"""
"""初始化管理员账号（直接运行脚本时使用）"""

import asyncio

import _bootstrap  # noqa: F401  将项目根目录加入 sys.path

from tortoise import Tortoise

from backend.configure import PROJECT_CONFIG
from backend.services.rag_security import get_password_hash
from backend.applications.user.models.user_model import User


def build_tortoise_config():
    return {
        "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
        "apps": {
            "models": {
                "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                "default_connection": "default"
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }


async def init_admin():
    await Tortoise.init(config=build_tortoise_config())

    existing = await User.get_or_none(username="admin")
    if existing:
        print("管理员账号已存在，更新密码...")
        existing.password = get_password_hash("admin")
        existing.is_active = True
        existing.is_superuser = True
        await existing.save()
    else:
        print("创建管理员账号...")
        await User.create(
            username="admin",
            alias="系统管理员",
            email="admin@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            password=get_password_hash("admin"),
            is_active=True,
            is_superuser=True,
        )

    await Tortoise.close_connections()
    print("✅ 管理员账号就绪！")
    print("   用户名: admin")
    print("   密码: admin")


if __name__ == "__main__":
    asyncio.run(init_admin())
