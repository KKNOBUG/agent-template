# -*- coding: utf-8 -*-
"""业务数据初始化（种子数据）。

对应 zsj 模板 core/initializations/data_initialization.py: zsj 在 lifespan 的
register_database 之后调用 init_database_table, 依次执行用户 / 模型配置 /
示例三个模块的 init_data 种子函数。

本项目已启用关系型业务数据（RagDocument 文档表与 RagConversation 对话三表均
持久化于 MySQL, 表结构由 Aerich 迁移建立）, 但当前无需要预置的种子数据
（文档与对话均由运行时产生, 旧环境存量经
services/scripts/migrate_json_to_mysql.py 一次性迁入）, 故本文件仅作结构占位:
    1. backend_main.py 的 lifespan 中依次调用 register_database / init_database_table
    2. 后续如需预置种子数据, 将各业务模块的 init_data 函数汇总到 init_database_table 内
"""
from fastapi import FastAPI


async def init_database_table(app: FastAPI):
    """汇总调用各业务模块的 init_data 种子函数（当前无需初始化的种子数据）。"""
    return None
