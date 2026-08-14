# -*- coding: utf-8 -*-
"""向量库 RPC 任务（Milvus Lite 单进程限制的桥接方案）。

Milvus Lite 为单进程嵌入式数据库, 同一时刻仅能被一个进程打开。
本模块在 Worker 进程内封装 Milvus 读写操作, Web 进程通过 Celery RPC
（send_task(...).get()）委托执行, 从而让 Web 与 Worker 共享同一 Milvus 实例。
"""
from typing import Any, Dict, List

from celery_scheduler.celery_worker import celery
from configure import LOGGER


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.query_chunks_rpc")
def query_chunks_rpc(query_vectors: List[List[float]], top_k: int = 60) -> List[Dict[str, Any]]:
    """RPC: 按向量相似度检索分块。"""
    from applications.jiayueyang.rag.milvus_store import query_chunks
    return query_chunks(query_vectors, top_k=top_k)


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.query_chunks_by_doc_rpc")
def query_chunks_by_doc_rpc(
        query_vectors: List[List[float]], doc_id: str, top_k: int = 8
) -> List[Dict[str, Any]]:
    """RPC: 在指定文档范围内按向量相似度检索分块（文档级召回定向注入）。"""
    from applications.jiayueyang.rag.milvus_store import query_chunks_by_doc
    return query_chunks_by_doc(query_vectors, doc_id, top_k=top_k)


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.get_all_chunks_rpc")
def get_all_chunks_rpc() -> List[Dict[str, Any]]:
    """RPC: 获取全部分块（供 BM25 混合检索建索引）。"""
    from applications.jiayueyang.rag.milvus_store import get_all_chunks
    return get_all_chunks()


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.delete_by_doc_rpc")
def delete_by_doc_rpc(doc_id: str) -> int:
    """RPC: 删除指定文档的全部分块。"""
    from applications.jiayueyang.rag.milvus_store import delete_by_doc_id
    deleted = delete_by_doc_id(doc_id)
    LOGGER.info(f"RPC 删除文档向量: doc_id={doc_id}, deleted={deleted}")
    return deleted


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.collection_stats_rpc")
def collection_stats_rpc() -> Dict[str, Any]:
    """RPC: 获取集合统计信息。"""
    from applications.jiayueyang.rag.milvus_store import get_collection_stats
    return get_collection_stats()


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.collection_fingerprint_rpc")
def collection_fingerprint_rpc() -> str:
    """RPC: 计算分块 ID 集合指纹（BM25 索引新鲜度判据）。

    指纹在 Worker 进程内计算, 仅回传短字符串——Web 侧凭指纹决定
    是否全量拉取重建 BM25, 稳态查询不再产生全量分块的跨进程传输。
    """
    from applications.jiayueyang.rag.milvus_store import get_collection_fingerprint
    return get_collection_fingerprint()


# ---------------------------------------------------------------------------
# 对话记忆（L4 向量回忆）RPC——独立集合 rag_chat_memory, 按 conversation_id 隔离
# ---------------------------------------------------------------------------

@celery.task(name="celery_scheduler.tasks.task_vector_rpc.upsert_chat_memory_rpc")
def upsert_chat_memory_rpc(records: List[Dict[str, Any]]) -> int:
    """RPC: 写入/更新对话轮次记忆向量。"""
    from applications.jiayueyang.rag.milvus_store import upsert_chat_memory
    return upsert_chat_memory(records)


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.search_chat_memory_rpc")
def search_chat_memory_rpc(
        query_vectors: List[List[float]],
        conversation_id: str,
        top_k: int = 3,
        max_seq: Any = None,
) -> List[Dict[str, Any]]:
    """RPC: 按向量相似度召回指定会话的旧轮次记忆。"""
    from applications.jiayueyang.rag.milvus_store import search_chat_memory
    return search_chat_memory(query_vectors, conversation_id, top_k=top_k, max_seq=max_seq)


@celery.task(name="celery_scheduler.tasks.task_vector_rpc.delete_chat_memory_rpc")
def delete_chat_memory_rpc(conversation_id: str) -> int:
    """RPC: 删除指定会话的全部对话记忆向量。"""
    from applications.jiayueyang.rag.milvus_store import delete_chat_memory_by_conv
    deleted = delete_chat_memory_by_conv(conversation_id)
    LOGGER.info(f"RPC 删除对话记忆: conversation_id={conversation_id}, deleted={deleted}")
    return deleted
