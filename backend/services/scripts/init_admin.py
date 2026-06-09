"""初始化管理员账号"""

import asyncio

import _bootstrap  # noqa: F401  将项目根目录加入 sys.path

from tortoise import Tortoise

from configure import TORTOISE_ORM
from services.rag_security import get_password_hash
from applications.rag_user.models.rag_user_model import User


async def init_admin():
    await Tortoise.init(config=TORTOISE_ORM)

    existing = await User.get_or_none(username="admin")
    if existing:
        print("管理员账号已存在，更新密码...")
        existing.hashed_password = get_password_hash("admin")
        existing.is_admin = True
        existing.is_active = True
        await existing.save()
    else:
        print("创建管理员账号...")
        await User.create(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin"),
            is_active=True,
            is_admin=True,
        )

    await Tortoise.close_connections()
    print("✅ 管理员账号就绪！")
    print("   用户名: admin")
    print("   密码: admin")


if __name__ == "__main__":
    asyncio.run(init_admin())
