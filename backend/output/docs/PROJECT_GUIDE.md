# ChatBoot 项目分析与扩展指南

> 企业级 RAG 问答系统 — 设计思想、代码逻辑、能力评估与后续扩展方向

---

## 一、项目定位与功能

### 1.1 是什么

ChatBoot（项目名 `xm1-aode-rag`）是一个**前后端分离的企业知识库智能问答系统**。核心能力是：将企业 PDF 文档向量化存入 Chroma，用户提问时先检索相关片段，再调用大语言模型（LLM）生成带上下文约束的回答。

典型场景：**员工手册问答、制度政策查询、内部文档助手**。

### 1.2 功能模块一览

| 模块 | 能力 | 入口 |
|------|------|------|
| 用户认证 | 注册、登录、JWT、管理员/普通用户 | `/api/auth/*` |
| 知识库管理 | 创建/删除知识库、公开/私有、PDF 上传 | `/api/knowledge-bases/*` |
| 文档处理 | PDF 解析 → 分块 → Embedding → Chroma 入库 | 上传接口同步处理 |
| 智能对话 | SSE 流式输出、多轮对话、选知识库/模型 | `/api/chat/stream` |
| 对话历史 | 会话列表、消息持久化、删除 | `/api/conversations/*` |
| 模型配置 | 模型名、temperature、max_tokens 等 | `/api/model-configs/*` |

### 1.3 前端页面

- **登录/注册**（`/login`）
- **对话页**（`/`）：选知识库、选模型、流式聊天
- **知识库管理**（`/knowledge-base`，仅 admin）：上传 PDF、管理文档与分块

---

## 二、系统架构

```
┌─────────────┐     HTTP/SSE      ┌──────────────────────────────────────┐
│  Vue 3 前端  │ ◄──────────────► │           FastAPI 后端                │
│  (Vite)     │   /api/* 代理     │  auth / chat / kb / history / model  │
└─────────────┘                   └───────────┬──────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              MySQL/SQLite              Chroma 向量库              外部 API
           (用户/会话/元数据)           (chunk 向量)           LLM + Embedding
```

### 2.1 一次完整问答的数据流

```
用户提问
  │
  ▼
chat_view.py：鉴权 → prepare_for_chat → 读取历史 Message
  │
  ▼
chain.rag_stream()
  ├─ (可选) 无关问题短路 → 固定话术回复
  ├─ _retrieve_context()：Embedding 问题 → Chroma 检索 top_k=5
  ├─ format_messages()：system + 历史(最近10轮) + user
  └─ OpenAICompatibleLLM.stream_chat()：OpenAI 兼容 API 流式生成
  │
  ▼
SSE 推送到前端 → 保存 assistant Message 到数据库
```

### 2.2 文档入库的数据流

```
PDF 上传
  │
  ▼
PyMuPDFLoader 解析 → RecursiveCharacterTextSplitter 分块
  │
  ├─ DocumentChunk 写入 MySQL（原文持久化）
  └─ get_embedding() 批量向量化 → chroma_store.upsert_chunks()
```

---

## 三、后端依赖库详解

### 3.1 核心框架

| 库 | 版本要求 | 作用 |
|----|----------|------|
| **fastapi** | ≥0.115 | Web 框架、路由、依赖注入 |
| **uvicorn** | ≥0.30 | ASGI 服务器 |
| **pydantic** / **pydantic-settings** | ≥2.0 | 请求/响应校验、配置模型 |
| **python-dotenv** | ≥1.0 | 加载 `.env` 环境变量 |

### 3.2 数据库

| 库 | 作用 |
|----|------|
| **tortoise-orm** | 异步 ORM，管理 User/KB/Conversation 等 |
| **aerich** | 数据库迁移（替代 Alembic） |
| **aiomysql** | MySQL 异步驱动（通过 Tortoise） |
| **aiosqlite** | SQLite 异步驱动（开发/测试默认） |
| **cryptography** | 加密相关（MySQL 等） |

### 3.3 RAG 与文档

| 库 | 作用 |
|----|------|
| **langchain** / **langchain-community** / **langchain-text-splitters** | PDF 加载、文本分块（未使用完整 Chain/Agent） |
| **pymupdf** | PDF 解析（通过 LangChain PyMuPDFLoader） |
| **chromadb** | Chroma 向量数据库客户端 |

### 3.4 认证与安全

| 库 | 作用 |
|----|------|
| **python-jose[cryptography]** | JWT 签发与验证 |
| **passlib[bcrypt]** | 密码哈希（实际使用 pbkdf2_sha256） |
| **python-multipart** | 文件上传 |

### 3.5 外部 API 与通信

| 库 | 作用 |
|----|------|
| **sse-starlette** | Server-Sent Events 流式响应 |
| **httpx** | LLM 流式 HTTP 调用（开发依赖，运行时使用） |
| **dashscope** | 千问 SDK（**已列入依赖，但当前 LLM 实现直接用 httpx/requests，未调用 dashscope**） |

### 3.6 开发/测试

| 库 | 作用 |
|----|------|
| **pytest** | 单元测试（项目暂无 tests 目录） |
| **httpx** | API 测试客户端 |

### 3.7 其他脚本

| 文件 | 说明 |
|------|------|
| `scripts/build_kb.py` | 离线构建知识库脚本（写入 Chroma 本地库） |

---

## 四、代码结构与职责

> **说明**：本节描述当前 **Tortoise ORM + 领域分包** 结构。早期单体 `app/` + SQLAlchemy 布局已废弃，勿再参照 `ARCHITECTURE.md` 中的旧目录树。

```
backend/
├── backend_main.py                 # FastAPI 入口、lifespan
├── configure/
│   ├── project_config.py           # 环境变量、TORTOISE_ORM、RAG 分块/检索参数
│   └── rag_config.py               # RAG_SYSTEM_PROMPT 等 Prompt 模板
├── core/
│   ├── initializations/            # 注册 Tortoise、路由、中间件、Aerich
│   ├── middlewares/                  # 鉴权、日志、请求上下文
│   ├── exceptions/                   # 统一 HTTP / 业务异常
│   └── chroma_db/                    # Chroma 持久化目录（本地向量库）
├── applications/                     # 按业务领域分包（models / schemas / services / views）
│   ├── base/
│   │   ├── views/
│   │   │   ├── auth_view.py          # 注册/登录/me
│   │   │   └── routes_view.py        # 健康检查等公共路由
│   │   ├── services/scaffold.py      # ScaffoldCrud 通用 CRUD 基类
│   │   └── rag/                      # RAG 子模块（与 FastAPI 解耦）
│   │       ├── chain.py              # 检索 → 拼 Prompt → 调 LLM（同步/流式）
│   │       ├── chroma_store.py       # Chroma 写入、检索、按 kb/doc/chunk 删除
│   │       ├── embeddings.py         # OpenAI 兼容 Embedding
│   │       ├── llm.py                # OpenAI 兼容 LLM + format_messages
│   │       └── loader.py             # 离线脚本用 PDF 加载工具
│   ├── user/
│   │   ├── models/user_model.py
│   │   ├── services/user_crud.py
│   │   └── views/user_view.py
│   ├── conversation/
│   │   ├── models/conversation_model.py   # Conversation、Message
│   │   ├── services/conversation_crud.py  # prepare_for_chat、stream_response
│   │   └── views/
│   │       ├── chat_view.py               # POST /chat/stream（SSE）
│   │       └── history_view.py            # 对话 CRUD
│   ├── knowledge_base/
│   │   ├── models/knowledge_base_model.py # KnowledgeBase、Document、DocumentChunk
│   │   ├── services/
│   │   │   ├── knowledge_base_crud.py     # 入库流水线、分块 CRUD
│   │   │   ├── document_loader.py         # 按 file_type 分发加载器
│   │   │   └── file_type.py               # 文件类型注册表（当前仅 PDF）
│   │   └── views/knowledge_base_view.py
│   └── model_config/
│       ├── models/model_config_model.py
│       ├── services/model_config_crud.py  # 列表按用户；聊天 resolve 降级 admin
│       └── views/model_config_view.py
├── migrations/models/              # Aerich 迁移脚本（0_init → …）
├── enums/                          # DocumentStatus、ChatMessageRole 等
└── services/                       # 密码哈希、初始化脚本、build_kb 等
```

### 4.1 分层与职责

| 层级 | 路径模式 | 职责 |
|------|----------|------|
| **views** | `applications/*/views/*_view.py` | HTTP 路由、参数校验、调用 Service、返回统一响应 |
| **services** | `applications/*/services/*_crud.py` | 业务编排、权限校验、跨表协调 |
| **models** | `applications/*/models/*_model.py` | Tortoise ORM 表结构与关系 |
| **schemas** | `applications/*/schemas/*_schema.py` | Pydantic 请求/响应 DTO |
| **rag** | `applications/base/rag/` | 向量检索、Prompt、LLM 调用（不依赖 FastAPI） |

典型调用链（聊天）：

```
chat_view.py → ConversationCrud.prepare_for_chat()
            → ConversationCrud.stream_response()
            → chain.rag_stream()
            → chroma_store.search() + llm.stream_chat()
```

### 4.2 设计思想

1. **领域分包**：用户、对话、知识库、模型配置各自独立，共享 `base/rag` 与 `ScaffoldCrud`。
2. **OpenAI 兼容接口**：LLM 与 Embedding 均通过 `/chat/completions`、`/embeddings` 调用，便于切换 DeepSeek、千问、硅基流动等。
3. **双存储**：MySQL/SQLite 存结构化元数据与原文分块；`core/chroma_db/` 存向量，检索时按 `kb_id`（支持 `$in` 多库）过滤。
4. **多租户轻量隔离**：知识库按 `user_id` + `is_public` 控制；模型配置列表按当前用户过滤，聊天时无个人配置则降级 admin 默认。
5. **降级友好**：Embedding 未配置时跳过检索，退化为纯 LLM 对话。
6. **迁移由 Aerich 管理**：模型变更后 `aerich migrate` → `aerich upgrade`（启动时也可自动执行，见 `app_initialization.py`）。

### 4.3 数据模型关系

```
User ─┬─ Conversation ─── Message (多轮对话，knowledge_base_ids: JSONField)
      ├─ KnowledgeBase ─── Document ─── DocumentChunk
      └─ ModelConfig (model_name、top_k、score_threshold 等)
```

### 4.4 相关设计文档

| 文档 | 主题 |
|------|------|
| `CHAT_KB_SELECTION.md` | 聊天侧知识库选择交互（待实现） |
| `RAG_RETRIEVAL_QUALITY.md` | 检索能力与 RAG 质量提升（待实现） |

---

## 五、现有能力评估

### 5.1 已具备

| 能力 | 实现程度 | 说明 |
|------|----------|------|
| 知识检索 (RAG) | ★★★☆☆ | 单向量检索 + top_k，无重排序/混合检索 |
| 会话记忆 | ★★☆☆☆ | 同会话内最近 10 轮消息注入 Prompt；无跨会话长期记忆 |
| 多模型管理 | ★★☆☆☆ | 可配 model_name/温度等；**API Key 全局单一，无按模型分 Provider** |
| 用户与权限 | ★★★☆☆ | JWT + admin/普通用户 + 知识库权限 |
| 流式体验 | ★★★★☆ | SSE 完整实现 |
| Skills | ☆☆☆☆☆ | 无 |
| MCP | ☆☆☆☆☆ | 无 |
| Agent 工具调用 | ☆☆☆☆☆ | 无 function calling / ReAct 循环 |

### 5.2 优点

1. **架构简洁**：FastAPI + Vue 经典组合，上手快，部署成本低。
2. **RAG 链路完整**：上传 → 分块 → 向量 → 检索 → 生成，闭环可用。
3. **Provider 解耦**：LLM/Embedding 通过 HTTP 抽象，换 DeepSeek 只需改 `.env`。
4. **异步数据库**：Tortoise ORM async，适合 I/O 密集场景。
5. **本地向量库**：Chroma 持久化到 `chroma_db/`，无需独立向量库服务。

### 5.3 缺点与风险

1. **文档处理同步阻塞**：大 PDF 上传在请求内处理，易超时，无 Celery/队列。
2. **仅支持 PDF**：Word、Markdown、网页等未覆盖。
3. **检索策略简单**：无 BM25 混合检索、无 Reranker、无引用溯源到具体页码。
4. **ModelConfig 不完整**：无 `provider`、`api_key`、`base_url` 字段，多 Provider 多 Key 无法数据库化管理。
5. **无测试**：缺少自动化测试，重构风险高。
6. **安全默认值弱**：CORS `*`、JWT 默认 Secret、`.env` 易误提交。
7. **LLM 与 Embedding 分离**：DeepSeek 无 Embedding，必须另配硅基流动等，增加运维复杂度。
8. **无关问题硬编码**：`is_irrelevant_question()` 用正则短路，扩展性差。

---

## 六、是否适合作为某系统的智能助手

### 6.1 适合的场景

- 企业内部 **文档问答**（员工手册、制度、FAQ）
- 需要 **私有化部署**、可控数据流的轻量助手
- 作为更大系统的 **RAG 子模块**（提供 `/api/chat/stream` 被其他系统调用）
- **MVP 阶段**快速验证知识库问答价值

### 6.2 不太适合直接使用的场景

- 需要 **调用业务 API、查数据库、发邮件** 的操作型助手（缺 Agent/Skills）
- 需要 **跨会话记住用户偏好** 的个人助理（缺长期记忆）
- 需要 **多租户 SaaS 级** 模型计费、按用户分配 Key
- 高并发、大文档量生产环境（缺任务队列、缺检索优化）

### 6.3 结论

**适合作为「知识问答型」智能助手的底座**，需二次开发才能升级为「全能型」业务助手。当前形态更接近 **Enterprise RAG Chatbot**，而非 **AI Agent Platform**。

---

## 七、扩展能力路线图

### 7.1 记忆（Memory）

**现状**：`format_messages()` 仅取 `chat_history[-10:]`，存在 MySQL `messages` 表。

**扩展方向**：

```
短期记忆（已有）          中期记忆                    长期记忆
会话内 N 轮消息      →   会话摘要压缩注入 Prompt   →   用户画像/偏好向量库
                         (Summary Buffer)              (独立 memory collection)
```

| 阶段 | 方案 | 改动点 |
|------|------|--------|
| P0 | 可配置窗口大小、Token 计数截断 | `chain.py` `format_messages()` |
| P1 | 会话结束生成摘要存 `Conversation.summary` | `chat_view.py` + `conversation_model.py` |
| P2 | 引入 LangGraph / 自研 MemoryStore，向量检索历史重要片段 | 新模块 `applications/base/memory/` |
| P3 | 用户级长期记忆表 + 权限隔离 | `UserMemory` ORM |

### 7.2 知识检索（RAG 增强）

**现状**：单路向量检索，chunk_size=500，top_k=5。

**扩展方向**：

| 能力 | 说明 |
|------|------|
| 混合检索 | BM25（Elasticsearch/Meilisearch）+ 向量，RRF 融合 |
| Reranker | bge-reranker 对 top_20 重排取 top_5 |
| 多格式文档 | Unstructured / LlamaParse 支持 Word/HTML |
| 引用溯源 | chunk metadata 存 page_num，回答附 `[来源: 文件名 p.12]` |
| 异步入库 | Celery + Redis 处理上传，WebSocket 推送进度 |
| Graph RAG | 实体关系图谱（长期） |

改动核心：`applications/base/rag/chain.py`、新增 `applications/base/rag/retriever.py`。详见 `RAG_RETRIEVAL_QUALITY.md`。

### 7.3 Skills（技能/工具）

**现状**：无工具调用，LLM 仅文本生成。

**扩展方向**：

```
用户问题
  │
  ▼
Agent Loop (ReAct / Tool Use)
  ├─ skill: search_knowledge_base  (现有 RAG)
  ├─ skill: query_database         (SQL with guardrails)
  ├─ skill: call_internal_api      (HTTP 工具)
  └─ skill: send_notification
  │
  ▼
汇总结果 → LLM 生成最终回复
```

| 阶段 | 方案 |
|------|------|
| P0 | 定义 `Tool` 基类 + OpenAI function calling | 新模块 `applications/base/agent/tools.py` |
| P1 | `chat_view.py` 改为 Agent 编排器，支持多轮 tool call |
| P2 | Skills 注册表（YAML/DB），admin 可启用/禁用 |
| P3 | 沙箱执行代码 Skill（需安全隔离） |

推荐依赖：`langgraph` 或自研轻量 ReAct 循环。

### 7.4 MCP（Model Context Protocol）

**现状**：无 MCP Server/Client。

**扩展方向**：

```
ChatBoot Backend
  │
  ├─ MCP Client ──► 连接外部 MCP Server（GitHub、Linear、数据库…）
  │                 动态发现 tools/resources
  │
  └─ MCP Server ──► 暴露本系统能力给 Cursor/Claude Desktop
                    tools: search_kb, upload_doc, list_conversations
```

| 阶段 | 方案 |
|------|------|
| P1 | 引入 `mcp` Python SDK，作为 Client 连接外部 Server |
| P2 | 将现有 KB 检索封装为 MCP Tool |
| P3 | 实现 ChatBoot MCP Server，供 IDE/其他 Agent 调用 |

改动点：新模块 `applications/base/mcp/`，与 `applications/base/agent/` 共用 Tool 抽象层。

### 7.5 多模型管理

**现状**：`ModelConfig` 仅存 `model_name` + 超参；Key/URL 在 `.env` 全局唯一。

**扩展方向**：

```python
# 建议扩展 ModelConfig 表
class ModelConfig:
    provider: str       # deepseek | dashscope | openai | siliconflow
    model_name: str
    api_key_enc: str    # 加密存储，或引用 Provider 配置
    base_url: str
    model_type: str     # llm | embedding | rerank
    is_default: bool
```

| 阶段 | 方案 |
|------|------|
| P1 | DB 增加 `provider` + `base_url`，`llm.py` 按配置实例化 |
| P2 | Provider 级 Key 管理（管理员配置，用户选用模型） |
| P3 | 路由策略：按任务类型自动选模型（chat vs embedding vs rerank） |
| P4 | 用量统计、限流、Fallback 链 |

---

## 八、推荐扩展架构（目标态）

```
                    ┌─────────────────────────────────┐
                    │         API Gateway / Auth       │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │      Agent Orchestrator          │
                    │  (ReAct / LangGraph / 状态机)     │
                    └───┬─────────┬─────────┬─────────┘
                        │         │         │
              ┌─────────▼──┐ ┌────▼────┐ ┌──▼──────────┐
              │ RAG Engine │ │ Memory  │ │ Tool/MCP    │
              │ 检索+重排   │ │ 短/长期  │ │ Skills 注册  │
              └─────────┬──┘ └────┬────┘ └──┬──────────┘
                        │         │         │
              ┌─────────▼─────────▼─────────▼──────────┐
              │     Model Router (多 Provider/多 Key)    │
              └──────────────────────────────────────────┘
                        │
              ┌─────────▼──────────────────────────────┐
              │  MySQL/SQLite  │  chroma_db/  │  Redis  │  Queue │
              └──────────────────────────────────────────┘
```

---

## 九、配置说明（当前）

```env
# LLM（对话）
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1
DEFAULT_LLM_MODEL=deepseek-chat

# Embedding（向量检索，与 LLM 独立）
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5

# 数据库
DB_TYPE=mysql          # 或 sqlite（默认）
MYSQL_HOST=...
```

---

## 十、快速定位问题

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| `LLM_API_KEY 未设置` | `.env` 未配置或未重启 | 检查 `configure/project_config.py` 加载 |
| `EMBEDDING_API_KEY 未设置` | 未配硅基流动 Key | 配 Key 或取消选知识库 |
| 选了知识库但回答不基于文档 | Chroma 无向量 / 未重新上传文档 | 看后端 `[Chroma]` 日志，重新上传 PDF |
| 上传 PDF 超时 | 同步处理大文件 | 改异步任务队列 |
| 模型配置列表为空但聊天仍可用 | 聊天降级使用 admin 默认配置 | 在「模型管理」为当前用户创建配置，或由 admin 维护默认配置 |
| 同 PDF 无法重传 | 已有 completed 记录占唯一约束 | 删除旧文档后再传；failed/processing 可直接同内容覆盖 |

---

## 十一、总结

ChatBoot 是一个**结构清晰、适合二次开发的企业 RAG 问答底座**。它在「文档入库 + 向量检索 + 流式对话 + 用户体系」上已具备可用闭环，但在 **Agent 能力（Skills/MCP）、长期记忆、高级检索、生产级任务调度、完整多模型治理** 方面仍有明显空间。

若目标是 **某业务系统的智能助手**：

- **短期**：直接用作知识问答模块，嵌入现有系统（iframe / API 集成）
- **中期**：补 Memory 摘要、Reranker、异步文档处理、ModelConfig 增强
- **长期**：引入 Agent 编排 + MCP + Skills 注册表，演进为可扩展的 AI 中台

---

## 十二、数据与运维约定（2026-06 更新）

- **数据库迁移**：`backend/migrations/models/` 下按序执行 `aerich upgrade`（init → 字段重命名 → JSON → 去 MaintainMixin 等）。
- **软删除**：`Conversation` / `KnowledgeBase` / `Message` 等 `state=1` 表示禁用/删除，用于统计留档，不提供应用内恢复。
- **文档删除**：`Document` / `DocumentChunk` 为物理删除；向量与本地文件同步清理。
- **RAG 参数**：全链路统一使用 `knowledge_base_ids`（Chroma 元数据仍为 `kb_id`）。

---

*文档版本：2026-06-11 | 基于 KeenRobot 当前代码*
