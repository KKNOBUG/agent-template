# -*- coding: utf-8 -*-
"""向量库访问代理（Web 端）。

Milvus Lite 模式下通过 Celery RPC 委托 Worker 独占访问；Milvus Server
模式下直接访问服务端，不再占用文档解析使用的 Celery 队列。
"""
from typing import Any, Dict, List, Optional

from configure import PROJECT_CONFIG

# RPC 等待超时统一取配置 VECTOR_RPC_TIMEOUT（需覆盖 Worker 池排队 + 操作耗时）

_TASK_PREFIX = "celery_scheduler.tasks.task_vector_rpc."


def _is_remote_milvus() -> bool:
    from applications.jiayueyang.rag.milvus_store import is_remote_milvus_uri

    return is_remote_milvus_uri()


def _direct_call(function_name: str, *args, **kwargs):
    from applications.jiayueyang.rag import milvus_store

    return getattr(milvus_store, function_name)(*args, **kwargs)


def _rpc_call(task_name: str, args=None):
    from celery_scheduler.celery_worker import celery

    return celery.send_task(
        _TASK_PREFIX + task_name,
        args=args,
    ).get(timeout=PROJECT_CONFIG.VECTOR_RPC_TIMEOUT)


def query_chunks(query_vectors: List[List[float]], top_k: int = 60) -> List[Dict[str, Any]]:
    if _is_remote_milvus():
        return _direct_call("query_chunks", query_vectors, top_k)
    return _rpc_call("query_chunks_rpc", [query_vectors, top_k])


def query_chunks_by_doc(
        query_vectors: List[List[float]], doc_id: str, top_k: int = 8
) -> List[Dict[str, Any]]:
    if _is_remote_milvus():
        return _direct_call("query_chunks_by_doc", query_vectors, doc_id, top_k)
    return _rpc_call("query_chunks_by_doc_rpc", [query_vectors, doc_id, top_k])


def get_all_chunks() -> List[Dict[str, Any]]:
    if _is_remote_milvus():
        return _direct_call("get_all_chunks")
    return _rpc_call("get_all_chunks_rpc")


def delete_by_doc_id(doc_id: str) -> int:
    if _is_remote_milvus():
        return _direct_call("delete_by_doc_id", doc_id)
    return _rpc_call("delete_by_doc_rpc", [doc_id])


def get_collection_stats() -> Dict[str, Any]:
    if _is_remote_milvus():
        return _direct_call("get_collection_stats")
    return _rpc_call("collection_stats_rpc")


def get_collection_fingerprint() -> str:
    if _is_remote_milvus():
        return _direct_call("get_collection_fingerprint")
    return _rpc_call("collection_fingerprint_rpc")


# ---------------------------------------------------------------------------
# 对话记忆（L4 向量回忆）——独立集合 rag_chat_memory, 按 conversation_id 隔离
# ---------------------------------------------------------------------------

def upsert_chat_memory(records: List[Dict[str, Any]]) -> int:
    if _is_remote_milvus():
        return _direct_call("upsert_chat_memory", records)
    return _rpc_call("upsert_chat_memory_rpc", [records])


def search_chat_memory(
        query_vectors: List[List[float]],
        conversation_id: str,
        top_k: int = 3,
        max_seq: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if _is_remote_milvus():
        return _direct_call("search_chat_memory", query_vectors, conversation_id, top_k, max_seq)
    return _rpc_call("search_chat_memory_rpc", [query_vectors, conversation_id, top_k, max_seq])


def delete_chat_memory(conversation_id: str) -> int:
    if _is_remote_milvus():
        return _direct_call("delete_chat_memory_by_conv", conversation_id)
    return _rpc_call("delete_chat_memory_rpc", [conversation_id])
