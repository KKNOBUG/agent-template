# 信用卡 RAG 智能问答系统

基于 **原生 IBM Docling（离线解析）+ FastAPI + Celery + Milvus + React** 的端到端 RAG 系统：PDF 离线解析、术语提取、递归字符分块、查询改写（指代消解 + LLM 术语改写）、多种检索模式、重排序、流式 AI 问答与对话历史管理。

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Celery](https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white)
![License](https://img.shields.io/badge/License-Private-lightgrey)

## 系统架构

```
生产: 浏览器 ──:80──▶ nginx ── /、/assets/*、/app.css、/fonts/* ──▶ web-heroui/dist（静态托管）
                       └─ /api、/docs、/swagger-assets ─反代─▶ FastAPI :8519（纯 API）
开发: 浏览器 ──:5174──▶ Vite（页面 + /api 代理）──────────────▶ FastAPI :8519

┌───────────────┐        ┌─────────────────────┐
│  Web (FastAPI) │ ─────▶ │  Redis (broker/结果) │
│  纯 API :8519  │  RPC   └──────────┬──────────┘
└───────┬───────┘                   │
        │ Milvus 操作经 Celery RPC 委托 │
        ▼                           ▼
┌───────────────────────────────────────┐
│         Celery Worker (线程池)          │
│  文档流水线: docling 离线解析 → 侧车      │
│  → 术语 → 分块 → 向量嵌入                │
│  独占访问 Milvus Lite (.milvus.db)       │
└───────────────────────────────────────┘
```

**关键设计**

- **原生 docling 离线解析**：docling 作为库运行于 Worker 进程内（非远程服务），模型全部来自本地 `docling_offline/docling/models/`，全程不联网。
- **源文件留档 + 消息仅传 job_id**：上传的 PDF 落盘至 `input/<job_id>/`（兼作重试源文件），Celery 消息仅携带 `job_id`，Worker 重读字节流解析，避免全文过消息队列；产物落在 `output/rag_upload/<job_id>/`。
- **Milvus Lite RPC 桥接**：Milvus Lite 为单进程嵌入式数据库，由 Worker 独占；Web 的检索/统计/删除经 Celery RPC 委托执行（`vector_rpc.py`），实现跨进程共享。
- **MySQL 持久化（Tortoise ORM + Aerich）**：文档状态（`rag_document`）、对话历史（`rag_conversation` / `rag_conversation_message` / `rag_conversation_retrieval` 三表，检索详情独立存表）、流水线状态与历史（`rag_pipeline_state` 单行表 / `rag_pipeline_history` 追加表）全部存于 MySQL，行级更新 + 事务天然防丢更新；连接配置见 `.env` 的 `DATABASE_*` 项，启动时自动建表/迁移。`rag_storage/` 文件存储已整体下线，旧 JSON 数据经 `services/scripts/migrate_json_to_mysql.py` 一次性迁移。
- **断点续传重试**：失败文档重试时若解析产物已存在，跳过解析直接从后处理阶段续跑。

## 技术栈

| 层 | 技术                                                                            |
|----|-------------------------------------------------------------------------------|
| 文档解析 | 原生 IBM Docling（离线）                                                            |
| 任务队列 | Celery 5 + Redis                                                              |
| 向量存储 | Milvus Lite / ChromaDB                                                        |
| 后端 | FastAPI + Loguru；MySQL 持久化（Tortoise ORM + Aerich；asyncmy 驱动）                  |
| LLM / 嵌入 / 重排 | OpenAI 兼容 API（DeepSeek / SiliconFlow）+ tenacity 重试；重排 BAAI/bge-reranker-v2-m3 |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS v4 + HeroUI v3                    |
| 大文件 | pypdf 自动切分 + Worker 内并行解析                                                     |

## 文档处理管线

```
上传 PDF ──Celery 任务──▶ Worker
  │
  ▼
内容解析     原生 docling 离线转换
  │          大文件自动切分并行处理（> PDF_SPLIT_MAX_PAGES 页）
  ▼
Sidecar      侧车文件（blocks / drawings / tables）
  ▼
文档摘要     LLM 结构化摘要 + 向量化（summary.json，供文档级召回，失败不致命）
  ▼
术语抽取     LLM 批量抽取术语对照表
  ▼
多模态分析   VLM 图片描述 + 表格摘要（可选，默认关闭）
  ▼
文档分块     递归字符分块 + 表格行分块
  ▼
向量嵌入     OpenAI 兼容 API 嵌入，写入 Milvus / ChromaDB
  ▼
complete     可检索问答
```

## 对话问答

- **查询模式**（`POST /api/query` 的 `mode`）：`hybrid`（BM25检索 + 向量检索 + 多文档摘要检索，RRF 融合）/ `naive`（向量检索）/ `bypass`（直连 LLM）。
- **检索增强流水线**（naive/hybrid 共用）：
  1. **指代消解**——多轮时用最近历史把当前问题消解为自包含查询（仅处理语法依赖，结果缓存 1 小时）；
  2. **术语改写**——术语索引三级词典匹配（精确/归一/二元字重叠）+ note 结构位置锚点（"数据元3的子域2" → 该位置的概念规范名），命中结果与全量术语表注入提示词，由 LLM（temperature=0）融合生成一行检索查询；匹配结果只作提示、绝不直接拼接，LLM 失败回退原始查询；改写结果缓存 1 小时（术语索引变化即清空）；
  3. **子查询分解**——复合问题拆为单面查询，每面独立召回，原查询保留作兜底；
  4. **多路召回 + 融合重排**——BM25检索 + 向量检索 + 多文档摘要检索，RRF 融合后经 `BAAI/bge-reranker-v2-m3` 重排（`RERANK_TOP_K` 窗口 + `RERANK_MIN_SCORE` 最低分过滤；长块切块打分、按块取 max 聚合）。
- **对话历史**：支持新建对话、历史列表（分"置顶"与"最近对话"两区）、置顶、重命名、删除。
- **多轮上下文**：服务端按 `conversation_id` 主动从会话存储读取最近 `CHAT_HISTORY_MAX_MESSAGES`（默认 20 条）历史，以独立多轮消息注入 LLM（系统提示词 → 历史 → 当前问题），长对话自动截断防上下文溢出。
- **流式输出**：`POST /api/query/stream` 以 SSE 逐 token 返回。
- **存储**：会话与消息持久化于 MySQL（`rag_conversation` / `rag_conversation_message`；AI 回答的检索详情独立存于 `rag_conversation_retrieval`），当前统一归属公共用户 `User`（预留后续接入真实用户体系）。

## 项目结构

```
agent-template-dev-jyy/
├── backend_main.py                  # FastAPI 入口（端口 8519）
├── gunicorn_config.py               # 生产 WSGI 配置（UvicornWorker）
├── celery_deploy.sh                 # 生产 Worker + Beat 启停脚本
├── .env / .env.example              # 环境变量配置（.env 不入库）
├── pyproject.toml / requirements.txt
│
├── applications/jiayueyang/         # RAG 业务应用
│   ├── dependencies.py              #   依赖注入工厂
│   ├── models/                      #   ORM 模型（rag_document / conversation 三表 / pipeline 两表）
│   ├── schemas/                     #   请求模型（rag_schema / chat_schema）
│   ├── views/                       #   API 路由（rag_view / chat_view）
│   ├── services/
│   │   ├── rag_service.py           #     文档状态管理（MySQL）
│   │   ├── rag_document_crud.py     #     文档表 CRUD
│   │   ├── rag_pipeline.py          #     处理流水线（含断点续传）
│   │   ├── chat_service.py          #     对话历史管理（MySQL）
│   │   ├── conversation_crud.py     #     对话三表 CRUD
│   │   ├── pipeline_crud.py         #     流水线状态/历史 CRUD（MySQL）
│   │   └── scaffold.py              #     ScaffoldModel/ScaffoldCrud 脚手架
│   └── rag/                         #   RAG 核心能力
│       ├── query.py                 #     检索问答引擎（hybrid/naive/bypass）
│       ├── query_rewriter.py        #     查询改写（指代消解 + 术语富集 + LLM 改写）
│       ├── llm.py / embedding.py / rerank.py / bm25.py / vlm.py
│       ├── doc_summary.py / doc_recall.py   #   文档级摘要生成与摘要召回
│       ├── chunker/                 #     分块策略
│       ├── milvus_store.py / vector_store.py / vector_rpc.py
│       ├── sidecar.py / multimodal.py / terminology.py
│       └── table_rows.py            #     表格行级分块（语义大纲栈命名）
│
├── celery_scheduler/                # Celery 任务体系
│   ├── celery_worker.py             #   Celery 应用（事件循环池）
│   ├── celery_base.py               #   Tortoise 幂等初始化
│   └── tasks/                       #   rag_pipeline / vector_rpc / rag_maintenance
│
├── services/                        # 项目级共享服务
│   ├── dependency.py                #   DependAuth（JWT 鉴权，默认未启用）
│   ├── ctx.py                       #   请求上下文（用户 ID 等）
│   └── scripts/                     #   工具脚本
│       ├── migrate_json_to_mysql.py #     旧 JSON 数据迁移入库（幂等）
│       ├── export_conversations.py  #     对话导出（CSV / JSON）
│       ├── backfill_doc_summary.py  #     文档摘要回填
│       ├── backfill_rag_update_fields.py # 增量更新字段回填
│       └── mem_probe.py             #     内存探测
│
├── common/                          # 通用工具
│   └── docling_native.py            #   原生 docling 离线转换封装
├── configure/                       # 配置中心（project / celery / rag / logging）
├── core/                            # 框架核心
│   ├── responses/                   #   统一响应信封
│   ├── exceptions/                  #   异常体系
│   ├── middlewares/                 #   中间件
│   ├── initializations/             #   启动初始化（建表/迁移等）
│   └── decorators/                  #   装饰器
│
├── web-heroui/                      # 前端（React 19 + TS + Vite + Tailwind v4 + HeroUI v3 + Zustand）
│   ├── src/ scripts/                #   源码与 CSS 降级构建管线（旧浏览器兼容）
│   └── dist/                        #   构建产物（nginx 托管，见 OFFLINE-DEPLOY.md）
├── deploy/nginx.conf                # 生产 nginx 配置（静态托管 + 反代后端）
├── static_vendor/swagger/           # 离线 Swagger UI / ReDoc 资源（/docs 依赖，随项目分发）
├── docling_offline/docling/models/  # docling 离线模型（不入 git）
├── input/                           # 上传 PDF 留档（按 job_id 组织）
├── output/rag_upload/               # 解析产物（按 job_id 组织）
└── .milvus.db/                      # Milvus Lite 数据库
```

---

## 环境要求

- Python = 3.13
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip
- Redis（任务调度必需）

## 快速开始

### 1. 环境准备

```powershell
cd D:\PycharmProjects\agent-template-dev-jyy
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

数据库迁移需要额外安装 Aerich：

```bash
pip install aerich
```

### 2. 准备 docling 离线模型

如果有 `docling-offline-models.zip` ，则直接解压至 `docling_offline/docling/models/`，否则需要以下指令进行下载：

```powershell
docling-tools models download
# 将 %USERPROFILE%\.cache\docling\models 的内容移入 docling_offline\docling\models\
```

### 3. 配置 .env

复制 `.env.example` 为 `.env`，按注释填写。

```ini
cp .env.example .env
```

最小可用示例：

```ini
# 向量数据库：milvus（默认，Worker 独占 + RPC）| chromadb（两端直连）
VECTOR_BACKEND=milvus
MILVUS_URI=./.milvus.db

# LLM 问答（OpenAI 兼容 API；字段名 LLM_BASE_URL 亦兼容旧名 LLM_API_BASE）
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=your-api-key

# 向量嵌入
EMBEDDING_BINDING_HOST=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BINDING_API_KEY=your-api-key

# 重排（OpenAI 兼容 rerank 端点）
RERANK_BINDING_HOST=https://api.siliconflow.cn/v1/rerank
RERANK_BINDING_API_KEY=your-api-key
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_TOP_K=50

# MySQL（应用只建表不建库，库需先手动创建）
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_NAME=your_db_name
DATABASE_USERNAME=your_username
DATABASE_PASSWORD=your_password

# Redis（Celery broker/backend）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# JWT（长度至少 64 位）
AUTH_SECRET_KEY=your-64+char-secret
```

### 4. 启动服务

```powershell
# 终端 1：Redis（本地启用需要运行，远程访问不需要）
redis-server --bind 127.0.0.1 --port 6379

# 终端 2：Celery Worker
celery -A celery_scheduler.celery_worker worker -Q default --pool=threads -c 4 -l INFO

# 终端 3：Web 服务（纯 API）
uvicorn backend_main:app --host 127.0.0.1 --port 8519
```

### 5. 前端

```powershell
cd web-heroui
npm install

# 开发模式（http://localhost:5174，/api 自动代理到 8519）
npm run dev

# 生产模式：构建到 web-heroui/dist，由 nginx 托管并反代后端（见 deploy/nginx.conf）
npm run build

# 仅预览构建产物（vite preview, 4173, 带 /api 代理）
npm run preview
```

---

## 环境变量参考

完整清单与注释见 `.env.example`（复制为 `.env` 后按需填写）。下表列出关键项：

| 变量 | 默认值 | 说明                                                        |
|------|--------|-----------------------------------------------------------|
| **解析 / 分块** | |                                                           |
| `PDF_SPLIT_MAX_PAGES` | `20` | PDF 切分阈值（超过此页数切分为多个子文档）                                   |
| `MAX_PARALLEL_PARSE_DOCLING` | `3` | 分片解析最大并行数                                                 |
| `DOCLING_PDF_BACKEND` | `pypdfium2` | PDF 内存后端：`pypdfium2`（大文档）/ `docling_parse`（默认）            |
| `DOCLING_USE_GPU` | `false` | docling 是否用 GPU（无 CUDA 版 torch 须置 false）                  |
| `CHUNK_SIZE` / `CHUNK_OVERLAP_SIZE` | `800` / `100` | 分块目标 token 数 / 相邻分块重叠 token 数                             |
| **LLM** | |                                                           |
| `LLM_BASE_URL` | — | LLM API 地址（OpenAI 兼容；兼容旧名 `LLM_API_BASE`）                 |
| `LLM_API_KEY` / `LLM_MODEL` | — / `deepseek-chat` | LLM Key / 模型名                                             |
| `LLM_TEMPERATURE` | `0.7` | 采样温度                                                      |
| `CHAT_HISTORY_MAX_MESSAGES` | `20` | 多轮上下文注入的兜底历史消息数                                           |
| **嵌入** | |                                                           |
| `EMBEDDING_BINDING_HOST` | `https://api.siliconflow.cn/v1` | 嵌入 API 地址                                                 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 嵌入模型                                                      |
| `EMBEDDING_DIM` | `1024` | 向量维度（Milvus 建集合使用）                                        |
| `EMBEDDING_BATCH_NUM` / `EMBEDDING_MAX_CONCURRENT` | `100` / `10` | 嵌入批量大小 / 最大并发                                             |
| **重排** | |                                                           |
| `RERANK_BINDING_HOST` | `https://api.siliconflow.cn/v1/rerank` | 重排 API 地址                                                 |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 重排模型                                                      |
| `RERANK_TOP_K` / `RERANK_MIN_SCORE` | `50` / `0.0` | 最终检索窗口条数 / 最低分阈值                                          |
| **文档级召回** | |                                                           |
| `DOC_RECALL_ENABLED` | `true` | 是否启用文档级召回（摘要索引 → 定向取分块）                                   |
| `DOC_RECALL_MIN_SCORE` | `0.5` | 查询向量与摘要向量的最低余弦相似度                                         |
| **向量库** | |                                                           |
| `VECTOR_BACKEND` | `milvus` | 后端选择：`milvus`（Milvus Lite）/ `chromadb`                    |
| `MILVUS_URI` | `./.milvus.db` | Milvus 连接（本地路径 = Milvus Lite；`http://host:19530` = 独立服务端） |
| **数据库 / Redis** | |                                                           |
| `DATABASE_HOST/PORT/NAME/USERNAME/PASSWORD` | —（必填） | MySQL 连接（任一缺失应用启动即报错）                                     |
| `DATABASE_AUTO_MIGRATION` | `true` | 启动时自动执行 aerich 迁移建表                                       |
| `REDIS_HOST` / `REDIS_PORT` | `127.0.0.1` / `6379` | Redis 连接（Celery broker/backend）                           |
| **鉴权** | |                                                           |
| `AUTH_SECRET_KEY` | — | JWT 签名密钥（长度至少 64 位，建议 `openssl rand -hex 32`）             |
| **VLM（可选）** | |                                                           |
| `ENABLE_VLM` | `false` | 是否启用 VLM 多模态分析                                            |
| `VLM_API_BASE` / `VLM_MODEL` | `http://127.0.0.1:11434/v1` / `gpt-4o` | VLM API 地址 / 模型名                                          |

---

## API 接口

所有接口返回统一信封 `{code, status, message, data, total}`，`code=000000` 为成功。

**文档与流水线**

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/engine/status` | 解析引擎状态（native/offline/模型路径） |
| `GET` | `/api/documents` | 文档列表 |
| `POST` | `/api/convert` | 上传 PDF，返回 job_id（后台 Celery 处理） |
| `GET` | `/api/convert/status/{job_id}` | 查询处理状态与进度 |
| `POST` | `/api/convert/retry` | 重试失败文档 |
| `POST` | `/api/files/delete` | 删除产物与文档记录（同步删向量） |
| `GET` | `/api/pipeline/status` | 流水线状态（进度 + 历史消息） |
| `POST` | `/api/pipeline/cancel` | 取消所有进行中的任务 |

**问答与对话**

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/query` | RAG 问答（非流式） |
| `POST` | `/api/query/stream` | RAG 问答（SSE 流式） |
| `GET` | `/api/models` | LLM 模型 + 向量库统计 |
| `GET` | `/api/conversations` | 会话列表（置顶优先 + 最近） |
| `POST` | `/api/conversations` | 新建会话 |
| `GET` | `/api/conversations/{id}/messages` | 会话历史消息 |
| `PATCH` | `/api/conversations/{id}` | 重命名会话 |
| `PATCH` | `/api/conversations/{id}/pin` | 置顶 / 取消置顶 |
| `DELETE` | `/api/conversations/{id}` | 删除会话 |

---

## 向量数据库

通过 `.env` 一行切换：

| | Milvus（默认） | ChromaDB |
|---|---|---|
| 存储位置 | `.milvus.db/` | `.chroma_db/` |
| 访问方式 | Worker 独占，Web 经 Celery RPC | Web/Worker 直接并发读写 |
| 适用 | 默认方案，数据量大 | 简单场景 |

- **Milvus Lite**（`MILVUS_URI` 为本地路径）：嵌入式单进程，故采用 Worker 独占 + RPC 桥接。
- **独立 Milvus 服务端**（`MILVUS_URI=http://host:19530`）：客户端-服务器架构，Web/Worker 直连（需 Docker 部署 Milvus Standalone）。

---

## 遗留问题

问题 1：
- 问题：所有操作共用一个 Worker，文档上传暂未实现先进先解析（FIFO）的串行队列。
- 原因：需要单独创建一个 Worker，但 Milvus Lite 不支持多线程，需更换为 Milvus Standalone。
