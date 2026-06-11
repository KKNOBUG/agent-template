# RAG 检索质量提升方案

> 状态：**设计稿 / 待实现**  
> 更新：2026-06-11  
> 关联：`CHAT_KB_SELECTION.md`（知识库范围）、`PROJECT_GUIDE.md` §7.2（路线图摘要）

---

## 一、背景与目标

### 1.1 问题

当前 RAG 链路为 **单向量检索 + 固定 top_k + 直接拼 Prompt**，在企业文档场景下常见：

- 关键词精确匹配弱（制度编号、专有名词、表格字段）
- 语义相近但无关片段排在前面（「年假」vs「病假」）
- 长 PDF 跨页答案被切碎，单 chunk 上下文不足
- 检索为空或分数偏低时仍走通用 LLM，用户难以察觉「未命中资料」
- 回答中的出处仅体现在 Prompt 上下文，**前端不可见、不可点击**

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 渐进增强 | 优先改索引与检索参数，再引入外部组件（ES、Rerank 服务） |
| 可观测 | 检索命中条数、分数、来源应在日志或 SSE 元数据中可追踪 |
| 配置分层 | 全局默认（`.env`）→ 知识库级（`chunk_size`）→ 模型配置（`top_k`/`score_threshold`） |
| 与选型解耦 | 知识库绑定方案见 `CHAT_KB_SELECTION.md`；本文聚焦「给定库集合后如何检得更好」 |
| 不破坏现有 API | 优先在后端 `chain` / `retriever` 内部扩展，前端引用展示为可选阶段 |

### 1.3 当前基线（已实现）

```
用户问题
  │
  ▼
chain._retrieve_context()
  ├─ is_embedding_configured() 未配置 → 跳过检索
  ├─ get_single_embedding(question)
  ├─ chroma_store.search(knowledge_base_ids, embedding, top_k)
  │     where: kb_id = x 或 kb_id $in [...]
  │     score = 1 - cosine_distance
  ├─ _filter_embedding_model_consistency()  # 过滤与 DEFAULT_EMBEDDING_MODEL 不一致的向量
  ├─ score_threshold 过滤（来自 ModelConfig，默认 0）
  └─ format_context_from_results()  # [n] (相关度) + 来源: 文件名 第N页
  │
  ▼
_resolve_system_prompt() + format_messages() + llm.stream_chat()
```

**入库侧**（`knowledge_base_crud._process_document`）：

- `RecursiveCharacterTextSplitter`，分隔符含中文标点
- 默认 `CHUNK_SIZE=500`、`CHUNK_OVERLAP=100`；知识库可覆盖
- 按 PDF **页** 遍历后再分块，`page_number` 写入 MySQL 与 Chroma metadata
- `embedding_model` 写入 Document 与 Chroma metadata

**关键参数来源**：

| 参数 | 默认 | 配置位置 |
|------|------|----------|
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 500 / 100 | `.env` 或 `KnowledgeBase.chunk_*` |
| `RETRIEVAL_TOP_K` | 5 | `.env`；聊天以 `ModelConfig.top_k` 为准 |
| `score_threshold` | 0.0 | `ModelConfig` |
| `DEFAULT_EMBEDDING_MODEL` | BAAI/bge-large-zh-v1.5 | `.env` |
| 历史轮数 | 10 | `chain.rag_stream(max_history_rounds)` 硬编码 |

---

## 二、质量短板拆解

| 环节 | 现状 | 典型影响 |
|------|------|----------|
| 分块 | 固定字符窗口，按页内切 | 条款跨页、表格行被截断 |
| 索引 | 仅 dense vector | 编号/缩写/精确词召回差 |
| 检索 | 单次 query embedding，top_k 直接进 Prompt | 问法多样时漏召 |
| 排序 | Chroma 距离序，无二次排序 | 噪声 chunk 占满 top_k |
| 阈值 | `score_threshold` 默认 0，几乎不过滤 | 低相关片段误导 LLM |
| 多库 | `$in` 合并检索，无 per-kb 配额 | 大库挤占小库结果 |
| 溯源 | Prompt 内有来源标签，无 API 回传 | 用户无法核对原文 |
| 模型切换 | 过滤不一致 embedding，无自动重建 | 换模型后有效库为空 |
| 评估 | 无离线评测集 | 改动难量化 |

---

## 三、方案总览

| 方案 | 作用阶段 | 收益 | 复杂度 | 依赖 |
|------|----------|------|--------|------|
| **A** 调参基线 | 检索 | 中 | 低 | 无 |
| **B** 分块策略增强 | 索引 | 高 | 低～中 | 无 |
| **C** Metadata / 父文档块 | 索引 | 中高 | 中 | 表结构可选扩展 |
| **D** 查询改写 / 多查询 | 检索前 | 中 | 中 | 额外 LLM 调用 |
| **E** 混合检索（BM25 + 向量） | 检索 | 高 | 中高 | ES/Meilisearch 或 SQLite FTS |
| **F** Rerank 重排 | 检索后 | 高 | 中 | Rerank API（如 bge-reranker） |
| **G** 检索结果 SSE 回传 + 前端引用 | 生成 | 中（体验） | 中 | 前端改动 |
| **H** Embedding 重建流水线 | 运维 | 必需（换模型时） | 中 | 后台任务 |
| **I** 离线评测集 | 工程 | 长期 | 中 | JSON/CSV + 脚本 |

**不推荐作为首期**：Graph RAG、ColBERT 多向量、完整 Agentic RAG 循环（成本高，与当前产品阶段不匹配）。

---

## 四、方案详述

### 方案 A：调参基线（零代码优先）

在不动架构前提下，用配置与运营验证上限。

**建议尝试**：

| 项 | 建议 | 说明 |
|----|------|------|
| `top_k` | 8～12 | 先放宽召回，为后续 Rerank 留候选 |
| `score_threshold` | 0.35～0.55 | 需按 bge + cosine 标定；过高会空召回 |
| `chunk_size` | 800～1200（制度类） | 减少条款断裂；overlap 保持 15%～20% |
| `max_history_rounds` | 可配置化 | 长对话时避免挤占 context 窗口 |

**改动点**：`ModelConfig` 已支持 `top_k` / `score_threshold`；知识库编辑页已支持 `chunk_size`（**改分块仅影响新上传文档**）。

**验收**：同一批 20～50 个真实问题，对比调整前后「人工判定可回答率」。

---

### 方案 B：分块策略增强

**思路**：在 `knowledge_base_crud._process_document` 替换或补充 splitter。

| 策略 | 做法 | 适用 |
|------|------|------|
| B1 结构感知 | 按 PDF 书签/标题层级先切段，再字符切 | 员工手册、章节目录清晰 |
| B2 段落优先 | 分隔符强化 `\n\n`、条款编号（第X条） | 制度文本 |
| B3 重叠加大 | overlap = min(200, chunk_size * 0.25) | 跨边界定义 |
| B4 表格单独处理 | 表格转 Markdown 整表为一块（体积上限） | 含福利表、薪资表 |

**实现草图**：

```python
# knowledge_base_crud._process_document
# 1. pages = load_document_pages(...)
# 2. sections = split_by_headings(pages)  # 可选
# 3. chunks = semantic_or_recursive_split(sections, chunk_size, chunk_overlap)
```

**注意**：变更分块后需 **重新上传或触发重建**，否则 Chroma 与 MySQL 旧块不一致。

---

### 方案 C：父块 + 子块（Parent-Document Retriever）

**思路**：索引用小 chunk 提高召回精度；命中后把 **父级大段** 或 **同页相邻块** 合并进 Prompt。

```
索引：child chunk (300～400 字) → Chroma
存储：parent_id / page_id 关联 MySQL
检索：命中 child → 拉取 parent 或 page 级拼接（上限 token）
```

**改动**：

- `DocumentChunk` 增加可选 `parent_chunk_id` 或 `section_id`
- `chroma_store.search` 返回 child 后，`retriever.expand_context(hit)` 合并
- Prompt 仍走 `format_context_from_results`

**收益**：显著缓解「检索到半句话」问题。  
**成本**：表结构迁移 + 入库逻辑调整。

---

### 方案 D：查询改写与多查询融合

**思路**：用户原问 → LLM 生成 1～3 个检索用 query（或 HyDE 虚构段落 embedding），分别检索后去重合并。

```
question
  ├─ embedding(q0)  → search → hits_0
  ├─ embedding(q1)  → search → hits_1   # 改写：同义/展开
  └─ embedding(q2)  → search → hits_2   # 关键词化
  └─ merge_dedupe_by_chunk_id → top N
```

**改动点**：新增 `applications/base/rag/query_transform.py`；`chain._retrieve_context` 调用。

**代价**：每条消息多 1 次 LLM 调用 + 多次 embedding，延迟与费用上升。  
**建议**：作为 **可选开关**（`ModelConfig` 或全局配置），默认关闭。

---

### 方案 E：混合检索（Sparse + Dense）

**思路**：BM25 擅精确词；向量擅语义。用 **RRF（Reciprocal Rank Fusion）** 合并两路结果。

```
                ┌─ BM25 index (doc_id/chunk_id → text)
question ───────┤
                └─ vector search (Chroma)
                          │
                          ▼
                    RRF merge → candidate top 20
```

**索引选型**：

| 引擎 | 优点 | 缺点 |
|------|------|------|
| **Meilisearch** | 轻量、中文友好 | 多一服务 |
| **Elasticsearch** | 成熟、可扩展 | 运维重 |
| **SQLite FTS5** | 零额外服务 | 与 Tortoise 同库，大数据量需调优 |
| **rank_bm25 内存** | 实现最快 | 重启重建、规模受限 |

**推荐路径**：开发期 **E-lite（SQLite FTS5 或内存 BM25）** 验证收益 → 生产再换 Meilisearch。

**改动**：

- 入库时同步写 BM25 索引（内容与 `DocumentChunk` 一致）
- 新增 `applications/base/rag/hybrid_retriever.py`
- `chain._retrieve_context` 改为调用 `HybridRetriever.retrieve()`

---

### 方案 F：Rerank 重排

**思路**：召回 `top_k_fetch`（如 20～30），用 Cross-Encoder Reranker 精排后取 `top_k`（5～8）进 Prompt。

```
candidates = hybrid_or_vector_fetch(k=30)
reranked = rerank_api(question, [c.content for c in candidates])
final = reranked[:top_k]
```

**模型**：`BAAI/bge-reranker-v2-m3`（硅基流动等同平台 API）、Cohere Rerank 等。

**配置扩展**（`ModelConfig` 或 `.env`）：

- `rerank_enabled: bool`
- `fetch_top_k: int`（召回数）
- `rerank_model: str`

**改动点**：`retriever.py` 增加 `rerank()`；`model_config` 表可选加字段。

**收益/成本比高**，适合在 A/B 调参后作为 **首期工程化增强**。

---

### 方案 G：检索结果回传与前端引用

**现状**：`format_context_from_results` 仅在 system prompt 内展示来源，SSE 只推 token。

**目标**：

1. 在 `meta` 或独立 `sources` 事件中返回结构化引用：

```json
{
  "type": "sources",
  "items": [
    {
      "index": 1,
      "score": 0.82,
      "filename": "员工手册.pdf",
      "page_number": 12,
      "chunk_id": "...",
      "snippet": "年假天数按工龄..."
    }
  ]
}
```

2. 前端在 assistant 消息下展示「参考来源」折叠区（可跳转文档预览页，若有）。

**改动**：

- `chain.rag_stream` 在流式开始前 `yield` 检索元数据（或 `chat_view` 先发 `sources` 事件）
- `conversation_crud.stream_response` 传递 `search_results`
- 可选：`Message` 表增加 `sources_json` 持久化

**与质量关系**：不直接提高召回，但降低「幻觉不可核对」体感，倒逼检索可解释。

---

### 方案 H：Embedding 模型一致性 / 重建

**现状**：

- 入库写入 `embedding_model`；检索时 `_filter_embedding_model_consistency` 丢弃不一致向量
- `chroma_store.py` 预留 reindex 注释，**无实现**

**换模型或升级维度后必须重建**，否则表现为「选了知识库但永远检不到」。

**建议流水线**：

```
reindex_kb(kb_id):
  for doc in kb.documents where status=completed:
    for chunk in doc.chunks:
      re-embed(chunk.content)
      chroma upsert (same chunk_id)
    update doc.embedding_model
```

**触发方式**：管理端「重建向量」按钮；或 `.env` 模型变更后 admin 批量任务（Celery 扩展点）。

---

### 方案 I：离线评测集

**思路**：维护 `eval/questions.jsonl`：`question`、`expected_doc`、`expected_keywords`、`kb_id`。

脚本对每个方案组合跑：

- Hit@k（期望 chunk 是否出现在 top_k）
- MRR / 平均分
- 可选：LLM-as-judge 回答质量

用于对比 A～F 改动，避免凭感觉调参。

---

## 五、推荐实施路线

### 组合 1：快速见效（1～2 天）

**A（调参）+ F（Rerank，fetch=20→top_k=5）**

- 不改索引结构
- `ModelConfig` 或 `.env` 增加 `FETCH_TOP_K`、`RERANK_ENABLED`
- 新增 `retriever.py` 封装「扩召回 + 重排」

### 组合 2：制度文档专项（3～5 天）

**B（结构分块）+ C（父块扩展）+ A**

- 针对 PDF 手册类明显提升
- 需重传文档或批量重建

### 组合 3：生产级检索（1～2 周）

**E-lite（SQLite FTS5 或 Meilisearch）+ F + G（来源 SSE）**

- 混合检索 + 重排 + 可观测引用
- 评测集 I 贯穿每次改动

### 组合 4：问法多样场景

**D（多查询，可选）+ F**

- 控制 LLM 调用成本（仅 `top_k` 召回差时触发）

---

## 六、模块划分建议（目标代码结构）

```
applications/base/rag/
├── chain.py              # 编排：无关问题短路、调用 retriever、拼 prompt、调 LLM
├── retriever.py          # 新增：统一 retrieve() 入口
├── hybrid_retriever.py   # 可选：BM25 + vector + RRF
├── reranker.py           # 可选：调用 Rerank API
├── query_transform.py    # 可选：改写 / 多查询
├── chroma_store.py       # 保持：向量读写
├── embeddings.py
└── llm.py
```

`chain._retrieve_context` 瘦身为：

```python
def _retrieve_context(question, knowledge_base_ids, *, top_k, score_threshold, ...):
    return retriever.retrieve(
        question=question,
        knowledge_base_ids=knowledge_base_ids,
        top_k=top_k,
        score_threshold=score_threshold,
    )
```

---

## 七、配置扩展建议

在现有 `ModelConfig` 上渐进增加（均可空，默认关闭）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `fetch_top_k` | int | 召回候选数，默认 20 |
| `rerank_enabled` | bool | 是否重排 |
| `rerank_model` | str | Rerank 模型名 |
| `hybrid_enabled` | bool | 是否启用 BM25 |
| `hybrid_weight` | float | 向量路与 BM25 融合权重（若不用 RRF） |
| `query_rewrite_enabled` | bool | 是否多查询 |

全局 `.env` 保留硬上限与默认值：`RETRIEVAL_FETCH_TOP_K`、`RERANK_MODEL` 等。

---

## 八、后端衔接注意事项

1. **检索参数来源**：聊天以 `conversation_crud.prepare_for_chat` 解析的 `ModelConfig` 为准，非知识库 `chunk_size`。
2. **多库检索**：Chroma `where kb_id $in` 为全局 top_k，必要时在 `retriever` 内做 **per-kb 配额**（如每库至少 2 条）。
3. **空召回策略**：维持现有「无上下文通用模式」，但建议 SSE 带 `retrieval_empty: true`，前端可提示「未在知识库中找到相关内容」。
4. **无关问题短路**：`is_irrelevant_question()` 仍 bypass 检索；与检索质量正交，后续可改为轻量分类模型。
5. **同步入库阻塞**：质量方案与 Celery 异步入库正交；重建索引任务更依赖队列（见 `PROJECT_GUIDE` §5.3）。
6. **知识库范围**：绑定哪些库由 `CHAT_KB_SELECTION.md` 方案决定；本文 retriever 只消费 `knowledge_base_ids: list[str]`。

---

## 九、实现优先级建议

| 阶段 | 内容 | 预估工作量 |
|------|------|------------|
| P0 | A：标定 `top_k` / `score_threshold` 推荐区间 + 文档说明 | 0.5 天 |
| P1 | F：Rerank + `fetch_top_k` + `retriever.py` 抽象 | 1～2 天 |
| P2 | G：SSE `sources` 事件 + 前端引用展示 | 1～2 天 |
| P3 | B：结构/段落分块 + 重传指引 | 1～2 天 |
| P4 | H：单库重建向量 API | 1 天 |
| P5 | E-lite：SQLite FTS5 混合检索 | 2～3 天 |
| P6 | C：父块扩展 | 2～3 天 |
| 可选 | D 多查询、I 评测集 | 按需 |

**当前决策**：暂不修改代码，待与 `CHAT_KB_SELECTION` 产品方向一并评审后，优先 **组合 1（A+F）** 开工。

---

## 十、验收要点（实现后）

- [ ] 同一评测集 Hit@5 相对基线提升（或 MRR 提升 ≥ 10%）
- [ ] Rerank 开启后，top_k 内噪声 chunk 比例下降（人工抽检）
- [ ] `score_threshold` 生效：低分 chunk 不进入 Prompt，且空召回有明确提示
- [ ] 换 Embedding 模型后，重建完成前 admin 可见「待重建」状态
- [ ] SSE `sources` 与最终回答引用一致（文件名、页码）
- [ ] 多库场景下小库文档仍有机会进入 top_k（若启用 per-kb 配额）
- [ ] 延迟：P95 增加可控（Rerank + 多查询需单独监控）

---

## 十一、相关代码索引

| 层级 | 路径 |
|------|------|
| 检索入口 | `backend/applications/base/rag/chain.py` → `_retrieve_context` |
| 向量库 | `backend/applications/base/rag/chroma_store.py` |
| Embedding | `backend/applications/base/rag/embeddings.py` |
| Prompt | `backend/configure/rag_config.py` |
| 入库分块 | `backend/applications/knowledge_base/services/knowledge_base_crud.py` → `_process_document` |
| 文档加载 | `backend/applications/knowledge_base/services/document_loader.py` |
| 检索参数 | `backend/applications/model_config/models/model_config_model.py` |
| 聊天编排 | `backend/applications/conversation/services/conversation_crud.py` |
| 流式 API | `backend/applications/conversation/views/chat_view.py` |
| 知识库选择 | `backend/output/docs/CHAT_KB_SELECTION.md` |

---

## 十二、待产品/技术确认

1. 首期更关注 **召回率** 还是 **回答可信度（溯源）**？决定 P1 是 F 还是 G。
2. 是否接受 Rerank 带来的 **额外 API 成本与 200～500ms 延迟**？
3. 制度类 PDF 是否占绝大多数？若是，可优先 B+C 而非 E。
4. 是否需要 **管理端「检索调试」**：输入问题即展示 top_k 片段与分数？
5. 换 Embedding 模型时，是否要求 **一键全库重建**（H）纳入首期？

确认后可从 **组合 1（A+F）** 或 **组合 2（B+C+A）** 择一开工。
