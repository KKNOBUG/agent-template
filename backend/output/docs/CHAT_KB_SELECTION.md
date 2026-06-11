# 聊天侧知识库选择方案

> 状态：**设计稿 / 待实现**  
> 更新：2026-06-11  
> 约束：**不在对话框、输入区展示知识库选择控件**

---

## 一、背景与目标

### 1.1 问题

当前聊天页（`frontend/src/views/chat/index.vue`）在后台静默加载知识库，并**自动选择列表第一个**（后端按 `updated_time` 倒序）。用户无法感知正在使用哪个库，也无法切换；多库场景下默认库往往不符合预期。

此前曾在输入区上方增加多选 `NSelect`，体验上侵入对话主区域，**已回退**。本文档记录替代方案，供后续迭代参考。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 对话框纯净 | 消息区 + 输入框不承载知识库配置 UI |
| 对话级绑定 | 知识库与 `conversation.knowledge_base_ids`（JSONField）绑定，历史对话可恢复 |
| 协议已就绪 | 前后端均支持 `knowledge_base_ids: string[]`，Chroma 支持多库 `$in` 检索 |
| 渐进增强 | 可先实现低成本方案（A/B），再按需扩展多选（C） |

### 1.3 当前数据流（基线）

```
页面加载 → fetchKnowledgeBases() → selectedKBs = [kbs[0].id]
新建对话 → selectedKBs 重置为 [knowledgeBases[0].id]
打开历史 → 从 detail.knowledge_base_ids 恢复 selectedKBs
发送消息 → chatStream(..., selectedKBs, ...) → POST /chat/stream（body: `knowledge_base_ids`）
```

后端 `prepare_for_chat`（`conversation_crud.py`）：

```python
if req.knowledge_base_ids is not None:
    knowledge_base_ids = req.knowledge_base_ids  # 传 [] 可清空绑定
else:
    knowledge_base_ids = self.get_knowledge_base_ids(conv)
# 非空时校验权限，并写回 conversation.knowledge_base_ids（JSONField）
```

RAG 检索（`chain.py` → `chroma_store.py`）按知识库 ID 列表过滤；为空则跳过向量检索，走通用对话。

---

## 二、方案总览

| 方案 | 交互位置 | 用户感知 | 改动量 | 适用场景 |
|------|----------|----------|--------|----------|
| **A** 知识库页「开始问答」 | 知识库管理页 | 弱（主动进入） | 小 | 按库专项咨询 |
| **B** 默认对话库 | 知识库编辑弹窗 | 几乎无 | 中 | 企业固定主库 |
| **C** 左侧栏配置区 | 对话列表上方 | 有，不占对话框 | 小～中 | 需切换 / 多选 |
| **D** URL / 本地记忆 | 路由参数、localStorage | 无 UI | 小 | 跳转、书签、记忆上次 |
| **E** 自动检索全部可见库 | 无 UI | 无 | 中（偏后端） | 库少、零配置 |
| **F** 欢迎区一次性选择 | 空对话 greeting 区 | 仅首条消息前 | 中 | 新对话时选一次 |
| **G** 对话列表只读标识 | 侧栏历史项 | 只展示 | 小 | 辨认历史绑定 |

**不推荐**：在输入框上方或输入框内嵌选择器（已明确排除）。

---

## 三、方案详述

### 方案 A：知识库页「开始问答」

**思路**：用户在管理页先选定资料库，再进入聊天；对话框无需任何控件。

**交互**

- 在 `knowledge-base/index.vue` 每个知识库卡片增加按钮「开始问答」
- 跳转：`/ai-manage/chat?kb=<kb_id>`  
  多库可扩展为：`?kb=id1,id2`

**聊天页改动**

```javascript
// onMounted / watch route.query.kb
const kbParam = route.query.kb
if (kbParam) {
  selectedKBs.value = String(kbParam).split(',').filter(Boolean)
}
```

**优点**：符合「先选库再问」心智；改动小；与现有 API 完全兼容。  
**缺点**：从菜单直接进入聊天时仍需默认策略（配合 B 或维持现状）。

**涉及文件**

- `frontend/src/views/knowledge-base/index.vue`
- `frontend/src/views/chat/index.vue`（读 query）
- 可选：`frontend/src/router` 无需改

---

### 方案 B：知识库级「默认对话库」

**思路**：仿 `ModelConfig.is_default`，为知识库增加默认标记；聊天页静默使用，无 UI。

**数据模型**

```python
# KnowledgeBase 新增字段（示例）
is_default_for_chat = fields.BooleanField(default=False, description="是否为默认对话知识库")
```

约束：每用户（或全局）仅允许一个 `is_default_for_chat=True`；设置时取消其它库的标记。

**管理页**

- 新建/编辑知识库弹窗增加「设为默认对话库」勾选
- 列表卡片可展示「默认」标签

**聊天页**

```javascript
// 优先级建议：URL 参数 > 对话已存 > 默认库 > 列表第一个
const defaultKb = kbs.find(k => k.is_default_for_chat)
selectedKBs.value = defaultKb ? [defaultKb.id] : (kbs[0] ? [kbs[0].id] : [])
```

**优点**：解决「第一个库不对」；对话框零控件；适合单一主库企业场景。  
**缺点**：需迁移 + 接口字段；多库同时检索需另做（E 或 C）。

**涉及文件**

- `backend/.../knowledge_base_model.py`
- `backend/.../knowledge_base_schema.py`
- `backend/.../knowledge_base_crud.py`（设置默认时互斥逻辑）
- `frontend/src/views/knowledge-base/index.vue`
- `frontend/src/views/chat/index.vue`
- Aerich 迁移

---

### 方案 C：左侧栏「对话设置」区（推荐：需多选时）

**思路**：在「新建对话」与历史列表之间增加知识库配置，与对话历史同级，不属于消息区。

**布局示意**

```
┌─────────────────┐
│  + 新建对话      │
├─────────────────┤
│ 知识库  [多选▼]  │  ← 仅此区域
├─────────────────┤
│ 对话1           │
│ 对话2           │
└─────────────────┘
```

**行为**

| 场景 | 行为 |
|------|------|
| 新建对话 | 侧栏选择初始化 `selectedKBs`（可用默认库 / localStorage） |
| 打开历史 | 从 `detail.knowledge_base_ids` 恢复并同步侧栏 |
| 侧栏切换 | 更新 `selectedKBs`，**下一条消息**起生效并写回对话记录 |
| 已有消息的对话 | 可选提示：「将应用于后续消息」 |

**优点**：支持多库；不污染输入区；类似侧栏选模型的习惯。  
**缺点**：侧栏略增复杂度。

**涉及文件**

- `frontend/src/views/chat/index.vue`（侧栏模板 + `NSelect multiple`）
- 样式：`.conversation-list` 上方新增 `.kb-sidebar-config`

---

### 方案 D：URL 参数 + localStorage 记忆

**思路**：无固定 UI，通过路由与本地存储传递选择。

**URL**

- `?kb=<id>` 或 `?kb=id1,id2`（与方案 A 共用）
- 新建对话时可 `router.replace` 带上当前 `selectedKBs`

**localStorage**（示例 key：`chat:last_knowledge_base_ids`）

- 每次成功发消息后写入
- 新建对话时读取；无则回退 B / 第一个

**优点**：实现快；可分享链接；与 A/B/C 任意组合。  
**缺点**：用户不可见，除非配合 G 或 C。

---

### 方案 E：后端自动检索全部可见库

**思路**：前端不传或传空时，后端拉取当前用户所有可访问知识库 ID 参与检索。

**后端改动**（`prepare_for_chat`）

```python
knowledge_base_ids = req.knowledge_base_ids or self.get_knowledge_base_ids(conv)
if not knowledge_base_ids:
    knowledge_base_ids = await kb_crud.list_accessible_ids(user)
```

**优点**：用户完全不用选；适合库总数少（如 &lt; 5）。  
**缺点**：库多时噪声大、检索慢；公开库与私有库混在一起需产品确认。

**涉及文件**

- `backend/.../conversation_crud.py`
- `backend/.../knowledge_base_crud.py`（新增 `list_accessible_ids`）

---

### 方案 F：欢迎区一次性选择

**思路**：仅在 `messages.length === 0` 时，在 greeting 下方展示知识库 chips；发出第一条消息后隐藏。

**优点**：新对话时可选一次，不长期占用界面。  
**缺点**：仍属对话主区域；若要求主区域完全纯净，不如 C 或 A。

**状态**：可作为 C 的轻量替代，非首选。

---

### 方案 G：侧栏对话项只读标识

**思路**：历史列表每项副标题展示绑定库名，如 `员工手册` 或 `2 个知识库`。

**数据来源**

- 列表接口返回 `knowledge_base_ids`，前端用已加载的 `knowledgeBases` 映射名称
- 或后端 `ConversationOut` 增加 `knowledge_names: string[]`（可选）

**优点**：帮助用户辨认历史对话；只读、无切换负担。  
**缺点**：不能单独解决问题，宜与 C 或 A 组合。

---

## 四、推荐组合

### 组合 1：单主库企业（推荐起步）

**B（默认对话库）+ A（从知识库页跳转）**

- 日常：用户无感，始终用默认库
- 专项：从某库卡片「开始问答」覆盖 URL 参数
- 对话框：零控件

### 组合 2：多库切换

**C（侧栏多选）+ G（历史标识）+ D（localStorage 记忆）**

- 侧栏配置当前会话使用的库
- 历史列表展示绑定关系
- 新建对话记住上次选择

### 组合 3：极致简单（库很少）

**E（自动全库）+ B（可选：默认库仅用于排序权重）**

- 前端可不再维护 `selectedKBs`
- 产品需接受跨库检索结果

---

## 五、后端衔接注意事项

实现任一方案时需保持与现有逻辑一致：

1. **请求优先**：`req.knowledge_base_ids is not None` 时使用请求值（含 `[]` 清空绑定）；未传则读会话已存值。
2. **存储类型**：`Conversation.knowledge_base_ids` 为 **JSONField**，ORM 直接读写 `list`，无需手动 JSON 编解码。
3. **持久化**：每次 `prepare_for_chat` 都会 `update_meta` 写回 `knowledge_base_ids`。
4. **权限**：`_validate_kb_access` 校验存在性 + 公开/所有者/超管。
5. **检索**：`top_k` / `score_threshold` 来自 `ModelConfig`，与知识库 `chunk_size` 无关。
6. **Embedding 一致性**：`chain._filter_embedding_model_consistency` 会过滤模型不一致的向量。

---

## 六、实现优先级建议

| 阶段 | 内容 | 预估工作量 |
|------|------|------------|
| P0 | 方案 B：默认对话库字段 + 编辑 UI + 聊天页读取 | 0.5～1 天 |
| P1 | 方案 A：知识库页「开始问答」+ URL 解析 | 0.5 天 |
| P2 | 方案 C：侧栏多选（若确认需要多库） | 0.5～1 天 |
| P3 | 方案 G：历史对话库名展示 | 0.5 天 |
| 可选 | D localStorage、E 全库自动检索 | 按需 |

**当前决策**：暂不修改代码，待产品确认组合后再按上表实施。

---

## 七、验收要点（实现后）

- [ ] 对话框/输入区无任何知识库选择控件
- [ ] 新建对话使用预期默认库（非「最近更新第一个」除非无默认）
- [ ] 从知识库页跳转后，首条消息检索命中目标库
- [ ] 历史对话打开后 `knowledge_base_ids` 与侧栏/行为一致
- [ ] 切换知识库后，后续消息检索范围正确更新
- [ ] 无权限 / 已删除知识库时，发消息有明确错误提示
- [ ] 多库检索时 Chroma `$in` 结果符合预期

---

## 八、相关代码索引

| 层级 | 路径 |
|------|------|
| 聊天页 | `frontend/src/views/chat/index.vue` |
| 知识库页 | `frontend/src/views/knowledge-base/index.vue` |
| 聊天 API | `frontend/src/api/index.js` → `chatStream` |
| 对话准备 | `backend/applications/conversation/services/conversation_crud.py` |
| 流式入口 | `backend/applications/conversation/views/chat_view.py` |
| RAG 检索 | `backend/applications/base/rag/chain.py` |
| 向量存储 | `backend/applications/base/rag/chroma_store.py` |
| 知识库列表 | `backend/applications/knowledge_base/services/knowledge_base_crud.py` → `list_for_user` |

---

## 九、待产品确认

1. 主场景是 **单一主库** 还是 **频繁多库切换**？
2. 从菜单直接进入聊天时，默认行为：默认库 / 全库检索 / 上次记忆？
3. 侧栏增加配置区是否可接受（方案 C）？
4. 历史对话是否允许中途更换知识库（仅后续消息生效）？

确认后可从 **组合 1（B+A）** 或 **组合 2（C+G+D）** 择一开工。
