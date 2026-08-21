# -*- coding: utf-8 -*-
"""向量库 RPC 代理（Web 端）。

Milvus Lite 同一时刻仅允许一个进程打开数据目录, 本模块把 Web 进程的
Milvus 操作通过 Celery RPC 委托给独占 Milvus 的 Worker 进程执行。
函数签名与 milvus_store 保持一致, 可作为直接替换导入使用。
"""
from typing import Any, Dict, List, Optional

from celery_scheduler.celery_worker import celery
from configure import PROJECT_CONFIG

# RPC 等待超时统一取配置 VECTOR_RPC_TIMEOUT（需覆盖 Worker 池排队 + 操作耗时）

_TASK_PREFIX = "celery_scheduler.tasks.task_vector_rpc."


def query_chunks(query_vectors: List[List[float]], top_k: int = 60) -> List[Dict[str, Any]]:
    """按向量相似度检索分块（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "query_chunks_rpc", args=[query_vectors, top_k]
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def query_chunks_by_doc(
        query_vectors: List[List[float]], doc_id: str, top_k: int = 8
) -> List[Dict[str, Any]]:
    """在指定文档范围内按向量相似度检索分块（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "query_chunks_by_doc_rpc",
        args=[query_vectors, doc_id, top_k],
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def get_all_chunks() -> List[Dict[str, Any]]:
    """获取全部分块（RPC 委托 Worker 执行, 供 BM25 建索引）。"""
    return celery.send_task(
        _TASK_PREFIX + "get_all_chunks_rpc"
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def delete_by_doc_id(doc_id: str) -> int:
    """删除指定文档的全部分块（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "delete_by_doc_rpc", args=[doc_id]
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def get_collection_stats() -> Dict[str, Any]:
    """获取集合统计信息（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "collection_stats_rpc"
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def get_collection_fingerprint() -> str:
    """获取分块 ID 集合指纹（RPC 委托 Worker 执行, 仅回传短字符串）。"""
    return celery.send_task(
        _TASK_PREFIX + "collection_fingerprint_rpc"
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


# ---------------------------------------------------------------------------
# 对话记忆（L4 向量回忆）——独立集合 rag_chat_memory, 按 conversation_id 隔离
# ---------------------------------------------------------------------------

def upsert_chat_memory(records: List[Dict[str, Any]]) -> int:
    """写入/更新对话轮次记忆向量（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "upsert_chat_memory_rpc", args=[records]
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def search_chat_memory(
        query_vectors: List[List[float]],
        conversation_id: str,
        top_k: int = 3,
        max_seq: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """按向量相似度召回指定会话的旧轮次记忆（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "search_chat_memory_rpc",
        args=[query_vectors, conversation_id, top_k, max_seq],
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def delete_chat_memory(conversation_id: str) -> int:
    """删除指定会话的全部对话记忆向量（RPC 委托 Worker 执行）。"""
    return celery.send_task(
        _TASK_PREFIX + "delete_chat_memory_rpc", args=[conversation_id]
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)
