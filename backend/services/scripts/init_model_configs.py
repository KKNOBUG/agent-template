# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : init_model_configs.py
@DateTime: 2025/4/28 18:07
"""
"""初始化 / 迁移 DeepSeek 模型配置（直接运行脚本时使用）"""

import asyncio

import _bootstrap  # noqa: F401  将项目根目录加入 sys.path

from tortoise import Tortoise

from backend.configure import PROJECT_CONFIG
from backend.applications.user.models.user_model import User
from backend.applications.model_config.models.model_config_model import ModelConfig

DEEPSEEK_CONFIGS = [
    {
        "name": "DeepSeek Chat",
        "model_name": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 0.95,
        "is_default": True,
    },
    {
        "name": "DeepSeek Reasoner",
        "model_name": "deepseek-reasoner",
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 0.95,
        "is_default": False,
    },
]


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


async def init_model_configs():
    await Tortoise.init(config=build_tortoise_config())

    admin = await User.get_or_none(username="admin")
    if not admin:
        print("❌ Admin 账号不存在，请先运行 init_admin.py")
        await Tortoise.close_connections()
        return

    print(f"找到 admin 账号 (ID: {admin.id})")
    existing = await ModelConfig.filter(user_id=admin.id).all()

    if existing:
        print(f"发现 {len(existing)} 个已有配置，迁移为 DeepSeek 模型...")
        for config in existing:
            old_name = config.model_name
            if config.is_default:
                config.name = "DeepSeek Chat"
                config.model_name = "deepseek-chat"
            elif "reasoner" in old_name.lower() or "plus" in old_name.lower():
                config.name = "DeepSeek Reasoner"
                config.model_name = "deepseek-reasoner"
            else:
                config.name = "DeepSeek Chat"
                config.model_name = "deepseek-chat"
            config.max_tokens = max(config.max_tokens, 4096)
            await config.save()
            print(f"  ✅ 更新: {old_name} -> {config.model_name}")
        print("\n✅ 模型配置已迁移为 DeepSeek！")
    else:
        print("创建 DeepSeek 模型配置...")
        for item in DEEPSEEK_CONFIGS:
            config = await ModelConfig.create(user_id=admin.id, **item)
            print(f"  ✅ 创建: {config.name} ({config.model_name})")
        print(f"\n✅ 成功创建 {len(DEEPSEEK_CONFIGS)} 个模型配置！")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(init_model_configs())
