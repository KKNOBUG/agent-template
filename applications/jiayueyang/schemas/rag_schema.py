# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class RetryConvert(BaseModel):
    """失败文档重试请求模型"""
    job_id: str = Field(..., description="文档任务ID")


class RollbackConvert(BaseModel):
    """失败文档回滚到上一版本请求模型（增量更新失败且 prev 归档齐备时可用）"""
    job_id: str = Field(..., description="文档任务ID")


class UpdateSummary(BaseModel):
    """更新文档摘要请求模型"""
    job_id: str = Field(..., description="文档任务ID")
    summary: str = Field(default="", max_length=15, description="文档摘要（用户编辑, 不超过15字）")


class QuerySelect(BaseModel):
    """RAG 问答请求模型"""
    query: str = Field(..., min_length=1, description="查询文本")
    mode: str = Field(default="naive", description="查询模式: naive(向量检索) / hybrid(混合检索) / bypass(直连对话)")
    response_type: str = Field(default="Multiple Paragraphs", description="回答呈现形式")
    chunk_top_k: Optional[int] = Field(default=None, ge=1, description="向量检索(naive 模式)稠密检索条数")
    rrf_top_k: Optional[int] = Field(default=None, ge=1, description="RRF 融合保留条数(hybrid 模式), 作为重排候选池")
    dense_top_k: Optional[int] = Field(default=None, ge=1, description="稠密向量检索条数(hybrid 模式)")
    bm25_top_k: Optional[int] = Field(default=None, ge=1, description="BM25 关键词检索条数(hybrid 模式)")
    max_total_tokens: Optional[int] = Field(default=None, ge=1, description="上下文 token 总预算")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    conversation_id: Optional[int] = Field(default=None, description="会话ID（传入则本轮问答持久化到该会话）")
    replace_message_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="重新生成: 复用会话中该下标的 assistant 消息槽位（需同时传 conversation_id, 不再追加新消息）",
    )
    user_prompt: Optional[str] = Field(default=None, description="用户附加指令")
    enable_rerank: bool = Field(default=True, description="是否启用重排序（跨编码器精排融合结果, 默认开启）")
    include_references: bool = Field(default=True, description="是否返回参考文献列表")
    temperature: Optional[float] = Field(default=None, ge=0, le=2, description="LLM 采样温度(0-2)")
    model: Optional[str] = Field(default=None, description="指定生成答案的 LLM 模型名（缺省用配置的 LLM_MODEL）")
