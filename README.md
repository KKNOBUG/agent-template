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
├── backend_main.py                 # FastAPI 入口
├── configure/
│   ├── config.py                   # ProjectConfig（pydantic-settings）
│   └── router_registry.py          # 路由注册信息
├── services/
│   ├── dependency.py               # 认证依赖（DependAuth）
│   ├── password.py                 # JWT / 密码工具
│   ├── ctx.py                      # 请求上下文（CTX_USER_ID）
│   ├── file_transfer.py            # 文件传输工具
│   └── scripts/                    # 运维脚本
│       ├── init_admin.py           # 初始化管理员
│       ├── init_model_configs.py   # 初始化模型配置
│       └── build_kb.py             # 离线构建向量库
├── applications/                   # 业务模块（models / schemas / services / views）
│   ├── base/                       # 基础服务
│   │   ├── database/               # Tortoise 初始化
│   │   ├── models/                 # ORM 模型聚合（供 Aerich 发现）
│   │   ├── rag/                    # RAG 链、向量库、LLM、Embedding
│   │   ├── services/               # 审计日志 CRUD
│   │   ├── schemas/                # 基础 schemas
│   │   └── views/                  # 认证、审计、路由视图
│   ├── user/                       # 用户与认证
│   ├── conversation/               # 对话与历史
│   ├── knowledge_base/             # 知识库与文档
│   └── model_config/               # LLM 模型参数配置
├── core/
│   ├── chroma_db/                  # ChromaDB 持久化目录
│   ├── rag_db/                     # SQLite 数据库目录（rag_system.db）
│   ├── initializations/            # 应用初始化（数据库、中间件、路由、异常）
│   ├── middlewares/                # 认证、日志、请求上下文中间件
│   ├── responses/                  # 统一响应封装
│   └── exceptions/                 # 自定义异常与处理器
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
# 假设当前在 KeenRobot/（backend 的上级目录）
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
uv run python backend_main.py
# 或
uvicorn backend_main:app --host 0.0.0.0 --port 8000 --reload
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

前端所有接口均以 `/api` 为前缀，请求时在 Header 携带 `token: <jwt_token>`。

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

### 认证 `/api/base/auth`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/base/auth/access_token` | 用户登录，返回 JWT | 否 |
| POST | `/api/base/auth/userinfo` | 获取当前用户信息 | 是 |

### 用户 `/api/user`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/user/create` | 用户注册 | 否 |
| POST | `/api/user/logout` | 用户登出（吊销 Token） | 是 |
| DELETE | `/api/user/delete` | 删除用户（Query: user_id） | 是 |
| POST | `/api/user/delete` | 批量删除用户 | 是 |
| POST | `/api/user/update` | 更新用户信息 | 是 |
| GET | `/api/user/get` | 查询用户详情（Query: user_id） | 是 |
| GET | `/api/user/byUsername` | 按用户名查询（Query: username） | 是 |
| GET | `/api/user/list` | 用户列表（分页查询） | 是 |
| POST | `/api/user/search` | 用户列表（Body 查询） | 是 |
| POST | `/api/user/update_password` | 修改密码 | 是 |
| POST | `/api/user/reset_password` | 重置密码 | 是 |

### 对话历史 `/api/conversations`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/conversations/` | 查询当前用户对话列表 | 是 |
| GET | `/api/conversations/{conversation_id}` | 查询对话详情（含消息） | 是 |
| DELETE | `/api/conversations/{conversation_id}` | 删除单条对话 | 是 |
| DELETE | `/api/conversations/` | 清空所有对话 | 是 |

### 聊天 `/api/chat`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/chat/stream` | SSE 流式问答 | 是 |

请求体示例：

```json
{
  "question": "公司的年假政策是什么？",
  "conversation_id": "可选，续聊时传入",
  "knowledge_base_ids": ["知识库ID"],
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

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/knowledge-bases/` | 创建知识库 | 是 |
| GET | `/api/knowledge-bases/` | 列表（支持 `?search=`） | 是 |
| GET | `/api/knowledge-bases/{kb_id}` | 详情 | 是 |
| PUT | `/api/knowledge-bases/{kb_id}` | 更新 | 是 |
| DELETE | `/api/knowledge-bases/{kb_id}` | 删除 | 是 |
| POST | `/api/knowledge-bases/{kb_id}/documents` | 上传 PDF | 是 |
| GET | `/api/knowledge-bases/{kb_id}/documents` | 文档列表 | 是 |
| DELETE | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` | 删除文档 | 是 |
| GET | `/api/knowledge-bases/{kb_id}/chunks` | 分块列表（Query: doc_id, page, page_size） | 是 |
| GET | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 分块详情 | 是 |
| PUT | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 更新分块 | 是 |
| DELETE | `/api/knowledge-bases/{kb_id}/chunks/{chunk_id}` | 删除分块 | 是 |

### 模型配置 `/api/model-configs`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/model-configs/` | 配置列表 | 是 |
| POST | `/api/model-configs/` | 创建配置 | 是 |
| GET | `/api/model-configs/default` | 获取默认配置 | 是 |
| GET | `/api/model-configs/{config_id}` | 配置详情 | 是 |
| PUT | `/api/model-configs/{config_id}` | 更新配置 | 是 |
| DELETE | `/api/model-configs/{config_id}` | 删除配置 | 是 |
| POST | `/api/model-configs/{config_id}/default` | 设为默认 | 是 |

列表仅返回**当前登录用户**自己创建的配置。聊天时优先使用用户指定/默认配置；若用户尚无配置，后端自动降级使用管理员（`admin`）的默认配置。

### 审计日志 `/api/base/audit`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/base/audit/list` | 审计日志列表（Query） | 是 |
| POST | `/api/base/audit/search` | 审计日志列表（Body） | 是 |
| GET | `/api/base/audit/get` | 单条审计日志 | 是 |
| GET | `/api/base/audit/byUser` | 用户审计日志 | 是 |
| GET | `/api/base/audit/recent` | 最近审计日志 | 是 |
| GET | `/api/base/audit/statistics` | 审计统计 | 是 |
| DELETE | `/api/base/audit/delete` | 删除单条 | 是 |
| POST | `/api/base/audit/delete` | 批量删除 | 是 |
| DELETE | `/api/base/audit/deleteByUser` | 按用户删除 | 是 |
| DELETE | `/api/base/audit/deleteByTime` | 按时间删除 | 是 |
| DELETE | `/api/base/audit/clearAll` | 清空所有 | 是 |

### 路由查询 `/api/base/routes`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/base/routes/routers` | 查询所有路由信息 | 是 |

## RAG 处理流程

```
用户提问
  → Embedding 向量化问题
  → ChromaDB 检索相关知识块（按 knowledge_base_ids 过滤）
  → 拼接上下文 + 历史消息
  → 调用 LLM 流式生成回答
  → 保存 assistant 消息到数据库
```

PDF 上传处理流程：

```
上传 PDF → PyMuPDF 解析 → 文本分块（500 字 / 100 重叠）
  → Embedding 向量化 → 写入 ChromaDB + 元数据入库
```

文档 `status`：`processing`（处理中）/ `completed`（成功）/ `failed`（失败）。同内容重传时，`failed` 或卡住的 `processing` 记录会被清理后覆盖；`completed` 仍拒绝重复上传。

对话/知识库等业务表使用 `state=1` 软删除，用于统计与留档，不提供前台恢复入口。

## 工具脚本

在项目根目录执行（需设置 `PYTHONPATH` 为包含 `backend` 包的上级目录）：

```bash
export PYTHONPATH="${PWD}"   # KeenRobot/

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
- `services/` — 认证、依赖注入、上下文
- `applications/base/rag/` — RAG 基础设施
- `core/` — 中间件、异常处理、响应封装、初始化

### 数据库初始化

`core/initializations/app_initialization.py` 在 FastAPI lifespan 中调用：

```python
register_tortoise(app=app, config=config, generate_schemas=False)
```

并自动执行 Aerich 迁移（生产环境 Linux 始终执行，开发环境 Windows 需开启 `DATABASE_AUTO_MIGRATION`）。

### 认证流程

1. 登录 `/api/base/auth/access_token` 获取 JWT
2. 后续请求在 Header 携带 `token: <jwt_token>`
3. `auth_middleware` 解析并验证 Token
4. `DependAuth` 依赖注入当前用户到视图函数
5. 登出 `/api/user/logout` 增加 `token_version` 吊销所有 Token

## 常见问题

### 启动报 `Module "aerich.models" not found`

安装 Aerich 后重启：

```bash
pip install aerich
```

或在 `configure/config.py` 的 `TORTOISE_ORM` 中移除 `aerich.models`（仅在不使用 Aerich 迁移时可临时处理）。

### 注册/登录报 `No TortoiseContext is currently active`

确认 `register_database()` 已正确调用 `register_tortoise`，并检查 lifespan 是否正常执行（启动日志中应有 `Application startup complete`）。

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
- **Script path**：`backend/backend_main.py`

## 与前端的功能对应

| 前端页面 | 后端模块 |
|----------|----------|
| `Login.vue` | `user` + `base/auth` — 注册 / 登录 |
| `Chat.vue` | `conversation` + `chat` — 流式问答、历史记录 |
| `KnowledgeBase.vue` | `knowledge_base` — 知识库与文档管理 |
| `ModelManage.vue` | `model_config` — 模型配置管理 |
| `Profile.vue` | `user` + `base/auth` — 用户信息展示 |

前端路由：

- `/login` — 登录注册
- `/` — 工作台
- `/ai-manage/chat` — 对话页
- `/knowledge-base` — 知识库管理
- `/ai-manage/model` — 模型配置管理
- `/profile` — 个人中心

---

## 前端接口调用详解

以下详细说明每个后端接口在前端中的调用方式、调用位置及交互逻辑。

### 一、认证相关接口

#### 1. `POST /api/base/auth/access_token` — 用户登录

**前端调用位置**：
- `frontend/src/views/login/index.vue` — `handleLogin()` 方法
- `frontend/src/api/index.js` — `login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true })`

**交互逻辑**：
1. 用户在登录页输入用户名和密码
2. 调用 `api.login({ username, password })`
3. 后端返回 `SuccessResponse` 包装的数据，前端提取 `data.access_token`
4. 通过 `setToken(token)` 将 Token 存入 localStorage
5. 调用 `userStore.getUserInfo()` 获取用户信息
6. 执行 `addDynamicRoutes()` 加载动态路由
7. 跳转至首页或重定向页面

**请求示例**：
```json
{
  "username": "admin",
  "password": "admin"
}
```

**响应示例**：
```json
{
  "code": "000000",
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "username": "admin",
    "alias": "管理员",
    "is_superuser": true
  }
}
```

---

#### 2. `POST /api/base/auth/userinfo` — 获取当前用户信息

**前端调用位置**：
- `frontend/src/store/modules/user/index.js` — `getUserInfo()` action
- `frontend/src/api/index.js` — `getUserInfo: () => request.post('/base/auth/userinfo')`

**交互逻辑**：
1. 登录成功后或页面刷新时自动调用
2. 后端返回当前登录用户的完整信息
3. 存入 Pinia store (`userStore.userInfo`)
4. 供全局组件使用（如 Header 显示用户名、头像等）

---

#### 3. `POST /api/user/create` — 用户注册

**前端调用位置**：
- `frontend/src/api/index.js` — `register: (data) => request.post('/user/create', data, { noNeedToken: true })`

**交互逻辑**：
1. 注册页面收集用户信息
2. 调用 `api.register(userData)`
3. 注册成功后通常自动跳转登录页

---

#### 4. `POST /api/user/logout` — 用户登出

**前端调用位置**：
- `frontend/src/store/modules/user/index.js` — `logout()` action
- `frontend/src/api/index.js` — `logout: () => request.post('/user/logout')`

**交互逻辑**：
1. 用户点击退出登录按钮
2. 调用 `api.logout()` 通知后端吊销 Token
3. 清除 localStorage 中的 Token
4. 重置 Pinia store、路由、标签页
5. 跳转至登录页

---

### 二、对话相关接口

#### 5. `GET /api/conversations/` — 查询对话列表

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `loadConversations()` 方法
- `frontend/src/api/index.js` — `fetchConversations: () => request.get('/conversations/').then(payload)`

**交互逻辑**：
1. 进入聊天页面时自动加载
2. 显示在左侧边栏的对话历史列表
3. 每条对话显示标题和删除按钮
4. 点击对话项可切换至该对话

---

#### 6. `GET /api/conversations/{conversation_id}` — 查询对话详情

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `loadConversation(id)` 方法
- `frontend/src/api/index.js` — `fetchConversation: (id) => request.get(\`/conversations/\${id}\`).then(payload)`

**交互逻辑**：
1. 点击左侧对话列表中的某条对话
2. 或从 URL `?conversation=xxx` 进入时调用
3. 加载该对话的所有历史消息
4. 恢复知识库选择 (`knowledge_base_ids`) 和模型配置 (`model_config_id`)
5. 消息渲染为气泡形式展示

---

#### 7. `DELETE /api/conversations/{conversation_id}` — 删除对话

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `handleDeleteConversation(id)` 方法
- `frontend/src/api/index.js` — `deleteConversation: (id) => request.delete(\`/conversations/\${id}\`).then(payload)`

**交互逻辑**：
1. 用户点击对话项旁的删除按钮
2. 弹出确认对话框
3. 确认后调用删除接口
4. 删除成功后刷新对话列表
5. 如删除的是当前对话，自动新建对话

---

#### 8. `POST /api/chat/stream` — SSE 流式问答

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `sendMessage()` 方法
- `frontend/src/api/index.js` — `chatStream()` 函数（独立导出）

**交互逻辑**：
1. 用户在输入框输入问题，按 Enter 发送
2. 调用 `chatStream(question, currentConvId, selectedKBs, selectedModelConfig, callbacks)`
3. 使用原生 `fetch` + `AbortController` 发起 SSE 请求
4. 实时接收 `event: token` 事件，逐字显示回答
5. 首次收到 `event: meta` 时获取 `conversation_id`，更新 URL
6. 收到 `event: done` 时标记回答完成，刷新对话列表
7. 用户可随时中断流式输出（调用 `controller.abort()`）

**请求示例**：
```json
{
  "question": "公司的年假政策是什么？",
  "conversation_id": "conv_abc123",
  "knowledge_base_ids": ["kb_xyz789"],
  "model_config_id": "cfg_def456"
}
```

**SSE 事件处理**：
```javascript
// onMeta: 获取 conversation_id，更新 URL
// onToken: 追加文本到消息气泡
// onDone: 完成标记，刷新列表
// onError: 显示错误提示
```

---

### 三、知识库相关接口

#### 9. `GET /api/knowledge-bases/` — 查询知识库列表

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `onMounted` 中加载（自动选择第一个知识库）
- `frontend/src/views/knowledge-base/index.vue` — `loadKnowledgeBases()` 方法
- `frontend/src/api/index.js` — `fetchKnowledgeBases: (search = '') => request.get(...).then(payload)`

**交互逻辑**：
- **聊天页**：加载后自动选择第一个知识库作为默认检索范围
- **知识库管理页**：展示所有知识库卡片，支持点击进入详情

---

#### 10. `POST /api/knowledge-bases/` — 创建知识库

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `handleCreateKB()` 方法
- `frontend/src/api/index.js` — `createKnowledgeBase: (data) => request.post('/knowledge-bases/', data).then(payload)`

**交互逻辑**：
1. 点击"新建知识库"按钮，弹出模态框
2. 输入名称、描述，选择是否公开
3. 调用创建接口
4. 成功后关闭模态框，刷新知识库列表

---

#### 11. `DELETE /api/knowledge-bases/{kb_id}` — 删除知识库

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `handleDeleteKB(id)` 方法
- `frontend/src/api/index.js` — `deleteKnowledgeBase: (id) => request.delete(\`/knowledge-bases/\${id}\`).then(payload)`

**交互逻辑**：
1. 点击知识库卡片上的删除按钮
2. 弹出确认对话框（`NPopconfirm`）
3. 确认后调用删除接口
4. 成功后刷新列表，清空右侧文档区域

---

#### 12. `POST /api/knowledge-bases/{kb_id}/documents` — 上传文档

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `handleUpload()` 方法
- `frontend/src/api/index.js` — `uploadDocument(kbId, file)` 函数（独立导出）

**交互逻辑**：
1. 选择知识库后，点击"上传文档"
2. 弹出上传模态框，选择 PDF 文件
3. 使用原生 `fetch` + `FormData` 上传（注意：使用 `token` Header 而非 `Authorization`）
4. 上传成功后刷新文档列表

**特殊说明**：
- 该接口使用原生 `fetch` 而非封装好的 `request`，因为需要处理文件上传
- Header 中携带 `token: <jwt_token>`

---

#### 13. `GET /api/knowledge-bases/{kb_id}/documents` — 查询文档列表

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `selectKB(kb)` 方法
- `frontend/src/api/index.js` — `fetchDocuments: (kbId) => request.get(\`/knowledge-bases/\${kbId}/documents\`).then(payload)`

**交互逻辑**：
1. 点击左侧知识库卡片
2. 右侧加载该知识库下的所有文档
3. 显示文档名、大小、状态标签

---

#### 14. `DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id}` — 删除文档

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `handleDeleteDoc(docId)` 方法
- `frontend/src/api/index.js` — `deleteDocument: (kbId, docId) => request.delete(\`/knowledge-bases/\${kbId}/documents/\${docId}\`).then(payload)`

**交互逻辑**：
1. 点击文档项旁的删除按钮
2. 弹出确认对话框
3. 确认后调用删除接口
4. 成功后刷新文档列表

---

#### 15. `GET /api/knowledge-bases/{kb_id}/chunks?doc_id={doc_id}` — 查询知识块列表

**前端调用位置**：
- `frontend/src/views/knowledge-base/index.vue` — `viewChunks(doc)` 方法
- `frontend/src/api/index.js` — `fetchChunks: (kbId, docId) => request.get(\`/knowledge-bases/\${kbId}/chunks?doc_id=\${docId}\`).then(payload)`

**交互逻辑**：
1. 点击文档项的"查看分块"按钮
2. 弹出模态框，显示该文档的所有分块
3. 每个分块显示序号和内容

---

### 四、模型配置相关接口

#### 16. `GET /api/model-configs/` — 查询模型配置列表

**前端调用位置**：
- `frontend/src/views/chat/index.vue` — `onMounted` 中加载（自动选择默认配置）
- `frontend/src/views/ai-manage/model/index.vue` — `fetchModelList()` 方法
- `frontend/src/api/index.js` — `fetchModelConfigs: () => request.get('/model-configs/').then(payload)`

**交互逻辑**：
- **聊天页**：加载后自动选择 `is_default=true` 的配置，或第一个配置
- **模型管理页**：在表格中展示所有配置，支持搜索过滤

---

#### 17. `POST /api/model-configs/` — 创建模型配置

**前端调用位置**：
- `frontend/src/views/ai-manage/model/index.vue` — `useCRUD` 的 `doCreate`
- `frontend/src/api/index.js` — `createModelConfig: (data) => request.post('/model-configs/', data).then(payload)`

**交互逻辑**：
1. 点击"新增"按钮，弹出表单模态框
2. 填写配置名称、模型名称、Temperature 等参数
3. 调用创建接口
4. 成功后刷新表格

---

#### 18. `PUT /api/model-configs/{config_id}` — 更新模型配置

**前端调用位置**：
- `frontend/src/views/ai-manage/model/index.vue` — `useCRUD` 的 `doUpdate`
- `frontend/src/api/index.js` — `updateModelConfig: (id, data) => request.put(\`/model-configs/\${id}\`, data).then(payload)`

**交互逻辑**：
1. 点击表格行的"编辑"按钮
2. 弹出表单模态框，回显当前数据
3. 修改后调用更新接口
4. 成功后刷新表格

---

#### 19. `DELETE /api/model-configs/{config_id}` — 删除模型配置

**前端调用位置**：
- `frontend/src/views/ai-manage/model/index.vue` — `useCRUD` 的 `doDelete`
- `frontend/src/api/index.js` — `deleteModelConfig: (id) => request.delete(\`/model-configs/\${id}\`).then(payload)`

**交互逻辑**：
1. 点击表格行的"删除"按钮
2. 弹出确认对话框（`NPopconfirm`）
3. 确认后调用删除接口
4. 成功后刷新表格

---

#### 20. `POST /api/model-configs/{config_id}/default` — 设为默认配置

**前端调用位置**：
- `frontend/src/views/ai-manage/model/index.vue` — `handleSetDefault(row)` 方法
- `frontend/src/api/index.js` — `setDefaultModelConfig: (id) => request.post(\`/model-configs/\${id}/default\`).then(payload)`

**交互逻辑**：
1. 点击表格行的"设为默认"按钮
2. 调用接口将该配置设为默认
3. 成功后刷新表格，显示新的默认标记

---

### 五、前端 API 封装说明

#### 请求封装 (`frontend/src/api/index.js`)

```javascript
import { request, getToken } from '@/utils'

// 普通 API 调用（使用封装的 request）
export default {
  login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.post('/base/auth/userinfo'),
  // ... 其他接口
}

// 文件上传（使用原生 fetch）
export async function uploadDocument(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: { token: getToken() },
    body: formData,
  })
  // ...
}

// SSE 流式聊天（使用原生 fetch + AbortController）
export function chatStream(question, conversationId, knowledgeIds, modelConfigId, callbacks) {
  const controller = new AbortController()
  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', token: getToken() },
    body: JSON.stringify({ question, conversation_id: conversationId, ... }),
    signal: controller.signal,
  })
  // ...
  return { abort: () => controller.abort() }
}
```

#### 认证方式

- **普通请求**：通过 `request` 封装自动在 Header 中添加 `token: <jwt_token>`
- **文件上传/SSE**：需手动调用 `getToken()` 获取 Token，放入 `token` Header
- **登录/注册**：标记 `noNeedToken: true`，不携带 Token

#### 响应格式

后端统一返回：
```json
{
  "code": "000000",
  "status": "success",
  "message": "操作成功",
  "data": { ... },
  "total": 100
}
```

前端通过 `payload(res)` 提取 `res.data` 或 `res`。

---

### 六、前端页面与接口映射总览

| 前端页面 | 路由 | 调用的后端接口 |
|----------|------|---------------|
| `Login.vue` | `/login` | `POST /api/base/auth/access_token` |
| | | `POST /api/user/create` (注册) |
| `Chat.vue` | `/ai-manage/chat` | `GET /api/conversations/` |
| | | `GET /api/conversations/{id}` |
| | | `DELETE /api/conversations/{id}` |
| | | `POST /api/chat/stream` |
| | | `GET /api/knowledge-bases/` |
| | | `GET /api/model-configs/` |
| `KnowledgeBase.vue` | `/knowledge-base` | `GET /api/knowledge-bases/` |
| | | `POST /api/knowledge-bases/` |
| | | `DELETE /api/knowledge-bases/{id}` |
| | | `GET /api/knowledge-bases/{id}/documents` |
| | | `POST /api/knowledge-bases/{id}/documents` |
| | | `DELETE /api/knowledge-bases/{id}/documents/{doc_id}` |
| | | `GET /api/knowledge-bases/{id}/chunks` |
| `ModelManage.vue` | `/ai-manage/model` | `GET /api/model-configs/` |
| | | `POST /api/model-configs/` |
| | | `PUT /api/model-configs/{id}` |
| | | `DELETE /api/model-configs/{id}` |
| | | `POST /api/model-configs/{id}/default` |
| `Profile.vue` | `/profile` | 使用 `userStore` 中的缓存数据 |
| Header/UserAvatar | 全局 | `POST /api/user/logout` |

---

*文档最后更新：2026-06-10*
