# KeenRobot 后端

企业级 RAG（检索增强生成）问答系统后端，基于 FastAPI 构建，提供用户认证、知识库管理、模型配置与流式智能问答能力。前端（Vue 3 + Vite）通过 `/api` 前缀调用本服务。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ORM | Tortoise ORM + Aerich（数据库迁移） |
| 关系型数据库 | SQLite（默认）/ MySQL |
| 向量数据库 | ChromaDB（本地持久化） |
| RAG | LangChain（文档加载、分块） |
| LLM | OpenAI 兼容 API（默认 DeepSeek） |
| Embedding | OpenAI 兼容 API（默认硅基流动） |
| 认证 | JWT + pbkdf2_sha256 密码哈希 |
| 流式输出 | SSE（sse-starlette） |
| 配置 | pydantic-settings |

## 项目结构

```
backend/
├── main.py                         # FastAPI 入口
├── configure/
│   └── config.py                   # ProjectConfig（pydantic-settings）
├── services/
│   ├── deps.py                     # 认证依赖（get_current_user）
│   ├── security.py                 # JWT / 密码工具
│   └── scripts/                    # 运维脚本
│       ├── init_admin.py           # 初始化管理员
│       ├── init_model_configs.py   # 初始化模型配置
│       └── build_kb.py             # 离线构建向量库
├── applications/                   # 业务模块（models / schemas / services / views）
│   ├── base/
│   │   ├── database/               # Tortoise 初始化
│   │   ├── models/                 # ORM 模型聚合（供 Aerich 发现）
│   │   ├── rag/                    # RAG 链、向量库、LLM、Embedding
│   │   └── views/router_view.py    # 路由汇总
│   ├── user/                       # 用户与认证
│   ├── conversation/               # 对话与历史
│   ├── knowledge_base/             # 知识库与文档
│   └── model_config/               # LLM 模型参数配置
├── core/
│   ├── chroma_db/                  # ChromaDB 持久化目录
│   └── rag_db/                     # SQLite 数据库目录（rag_system.db）
├── output/data/                    # 离线脚本示例 PDF 目录
├── uploads/                        # 用户上传文档存储
├── migrations/                     # Aerich 迁移文件
├── .env                            # 环境变量（需自行创建）
└── pyproject.toml                  # Python 依赖（uv / pip）
```

## 环境要求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip
- Node.js >= 16（仅前端联调时需要）

## 快速开始

### 1. 安装依赖

```bash
cd backend
uv sync
# 或
pip install -e .
```

数据库迁移需要额外安装 Aerich：

```bash
uv add aerich
# 或
pip install aerich
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `backend/.env`，至少配置：

- `AUTH_SECRET_KEY`：JWT 密钥，**长度不少于 64 位**（可用 `openssl rand -hex 32` 生成）
- `LLM_API_KEY`：大模型 API Key（如 DeepSeek）
- `EMBEDDING_API_KEY`：向量模型 API Key（如硅基流动，知识库检索必需）

完整配置项见 [环境变量说明](#环境变量说明)。

### 3. 初始化数据库

**首次部署**（在项目根目录执行，`PYTHONPATH` 指向包含 `backend` 包的目录）：

```bash
# 假设当前在 KeenRobot_副本/（backend 的上级目录）
export PYTHONPATH="${PWD}"

cd backend
aerich init -t backend.configure.config.TORTOISE_ORM
aerich init-db
```

若已有迁移文件（`migrations/` 目录），直接升级：

```bash
aerich upgrade
```

### 4. 初始化业务数据

```bash
# 仍在项目根目录，PYTHONPATH 已设置
python backend/services/scripts/init_admin.py
python backend/services/scripts/init_model_configs.py
```

默认管理员账号：

| 字段 | 值 |
|------|-----|
| 用户名 | admin |
| 密码 | admin |

### 5. 启动后端

```bash
cd backend
uv run python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：

- 健康检查：http://localhost:8000/api/health
- Swagger 文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### 6. 启动前端（联调）

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 http://localhost:3001，并通过 Vite 代理将 `/api` 转发到 `http://localhost:8000`：

```js
// frontend/vite.config.js
proxy: { '/api': { target: 'http://localhost:8000' } }
```

前端所有接口均以 `/api` 为前缀，请求时在 Header 携带 `Authorization: Bearer <token>`。

## 环境变量说明

配置文件路径：`backend/.env`（由 `configure/config.py` 中的 `ProjectConfig` 加载）。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_TYPE` | 数据库类型：`sqlite` / `mysql` | `sqlite` |
| `DATABASE_HOST` | MySQL 主机（兼容 `MYSQL_HOST`） | `localhost` |
| `DATABASE_PORT` | MySQL 端口（兼容 `MYSQL_PORT`） | `3306` |
| `DATABASE_USERNAME` | MySQL 用户名（兼容 `MYSQL_USER`） | `rag_user` |
| `DATABASE_PASSWORD` | MySQL 密码（兼容 `MYSQL_PASSWORD`） | `password` |
| `DATABASE_NAME` | MySQL 库名（兼容 `MYSQL_DATABASE`） | `rag_system` |
| `AUTH_SECRET_KEY` | JWT 密钥（兼容 `SECRET_KEY`，≥64 位） | — |
| `AUTH_JWT_ALGORITHM` | JWT 算法（兼容 `ALGORITHM`） | `HS256` |
| `AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token 过期时间（分钟） | `30` |
| `LLM_API_KEY` | 大模型 Key（兼容 `DASHSCOPE_API_KEY`） | — |
| `LLM_BASE_URL` | 大模型 API 地址 | `https://api.deepseek.com/v1` |
| `DEFAULT_LLM_MODEL` | 默认模型名 | `deepseek-chat` |
| `EMBEDDING_API_KEY` | 向量模型 Key（兼容 `SILICONFLOW_API_KEY`） | — |
| `EMBEDDING_BASE_URL` | 向量 API 地址 | `https://api.siliconflow.cn/v1` |
| `DEFAULT_EMBEDDING_MODEL` | 默认 Embedding 模型 | `BAAI/bge-large-zh-v1.5` |
| `CHROMA_COLLECTION` | Chroma 集合名 | `knowledge_base` |

SQLite 模式下，数据库文件位于 `core/rag_db/rag_system.db`；向量数据位于 `core/chroma_db/`。

代码中通过单例访问配置：

```python
from backend.configure.config import PROJECT_CONFIG, TORTOISE_ORM
```

## API 接口

以下接口与前端 `frontend/src/api/index.js` 一一对应。

### 健康检查

| 方法 | 路径 | 认证 |
|------|------|------|
| GET | `/api/health` | 否 |

### 认证 `/api/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/me` | 获取当前用户信息 |
| POST | `/api/auth/logout` | 登出 |

### 对话 `/api/conversations`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations/` | 对话列表 |
| GET | `/api/conversations/{id}` | 对话详情（含消息） |
| DELETE | `/api/conversations/{id}` | 删除单条对话 |
| DELETE | `/api/conversations/` | 清空全部对话 |

### 聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | SSE 流式问答 |

请求体示例：

```json
{
  "question": "公司的年假政策是什么？",
  "conversation_id": "可选，续聊时传入",
  "kb_ids": ["知识库ID"],
  "model_config_id": "可选"
}
```

SSE 事件类型：

| event | 含义 |
|-------|------|
| `meta` | 返回 `conversation_id` |
| `token` | 流式文本片段 |
| `done` | 回答完成 |
| `error` | 错误信息 |

### 知识库 `/api/knowledge-bases`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge-bases/` | 创建知识库 |
| GET | `/api/knowledge-bases/` | 列表（支持 `?search=`） |
| GET | `/api/knowledge-bases/{kb_id}` | 详情 |
| PUT | `/api/knowledge-bases/{kb_id}` | 更新 |
| DELETE | `/api/knowledge-bases/{kb_id}` | 删除 |
| POST | `/api/knowledge-bases/{kb_id}/documents` | 上传 PDF |
| GET | `/api/knowledge-bases/{kb_id}/documents` | 文档列表 |
| DELETE | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` | 删除文档 |
| GET | `/api/knowledge-bases/{kb_id}/chunks` | 分块列表 |
| GET | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 分块详情 |
| PUT | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 更新分块 |
| DELETE | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 删除分块 |

### 模型配置 `/api/model-configs`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/model-configs/` | 配置列表 |
| POST | `/api/model-configs/` | 创建配置 |
| GET | `/api/model-configs/default` | 获取默认配置 |
| GET | `/api/model-configs/{id}` | 配置详情 |
| PUT | `/api/model-configs/{id}` | 更新配置 |
| DELETE | `/api/model-configs/{id}` | 删除配置 |
| POST | `/api/model-configs/{id}/default` | 设为默认 |

## RAG 处理流程

```
用户提问
  → Embedding 向量化问题
  → ChromaDB 检索相关知识块（按 kb_ids 过滤）
  → 拼接上下文 + 历史消息
  → 调用 LLM 流式生成回答
  → 保存 assistant 消息到数据库
```

PDF 上传处理流程：

```
上传 PDF → PyMuPDF 解析 → 文本分块（500 字 / 100 重叠）
  → Embedding 向量化 → 写入 ChromaDB + 元数据入库
```

## 工具脚本

在项目根目录执行（需设置 `PYTHONPATH` 为包含 `backend` 包的上级目录）：

```bash
export PYTHONPATH="${PWD}"   # KeenRobot_副本/

# 初始化管理员
python backend/services/scripts/init_admin.py

# 初始化 DeepSeek 模型配置
python backend/services/scripts/init_model_configs.py

# 离线构建向量库（读取 output/data/*.pdf）
python backend/services/scripts/build_kb.py
```

## 架构说明

### 模块化分层

每个业务域（`user`、`conversation`、`knowledge_base`、`model_config`）均包含：

- `models/` — Tortoise ORM 模型
- `schemas/` — Pydantic 请求/响应模型
- `services/` — 业务逻辑与数据访问
- `views/` — FastAPI 路由（API 层）

公共能力集中在：

- `configure/` — 应用配置
- `services/` — 认证、依赖注入
- `applications/base/rag/` — RAG 基础设施

### 数据库初始化

`applications/base/database/init_db.py` 在 FastAPI lifespan 中调用：

```python
await Tortoise.init(config=TORTOISE_ORM, _enable_global_fallback=True)
```

Tortoise ORM 1.1.7 起使用上下文隔离，FastAPI lifespan 运行在独立 task 中，必须启用 `_enable_global_fallback=True`，否则请求处理时会报 `No TortoiseContext is currently active`。

## 常见问题

### 启动报 `Module "aerich.models" not found`

安装 Aerich 后重启：

```bash
pip install aerich
```

或在 `configure/config.py` 的 `TORTOISE_ORM` 中移除 `aerich.models`（仅在不使用 Aerich 迁移时可临时处理）。

### 注册/登录报 `No TortoiseContext is currently active`

确认 `init_db()` 使用了 `_enable_global_fallback=True`，并检查 lifespan 是否正常执行（启动日志中应有 `Application startup complete`）。

### 知识库问答不检索文档

检查 `.env` 中是否配置了 `EMBEDDING_API_KEY`。未配置时系统会跳过向量检索，退化为纯 LLM 对话。

### 切换 MySQL

```env
DB_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_USERNAME=rag_user
DATABASE_PASSWORD=your_password
DATABASE_NAME=rag_system
```

修改后重新执行 `aerich upgrade`。

### PyCharm 调试

- **Working directory**：`backend/`
- **PYTHONPATH**：添加 `backend` 的上级目录（使 `import backend` 可用）
- **Script path**：`backend/main.py`

## 与前端的功能对应

| 前端页面 | 后端模块 |
|----------|----------|
| `Login.vue` | `user` — 注册 / 登录 |
| `Chat.vue` | `conversation` — 流式问答、历史记录 |
| `KnowledgeBase.vue` | `knowledge_base`、`model_config` — 知识库与模型管理 |

前端路由：

- `/login` — 登录注册
- `/` — 对话页
- `/knowledge-base` — 知识库管理
