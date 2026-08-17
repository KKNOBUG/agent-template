# -*- coding: utf-8 -*-
"""ChromaDB 持久化向量存储，接口设计参考 LightRAG

支持多文档存储，并携带 file_path 元数据用于引用溯源。
"""

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from configure import LOGGER, PROJECT_CONFIG

_COLLECTION = "documents"

# 存量集合度量告警只打一次（查询路径每次都会取集合, 避免日志刷屏）
_L2_SPACE_WARNED = False


def _get_client() -> chromadb.PersistentClient:
    """创建 ChromaDB 持久化客户端（数据目录位于输出目录同级）"""
    path = str(Path(PROJECT_CONFIG.OUTPUT_DIR) / ".." / ".chroma_db")
    Path(path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=path, settings=Settings(anonymized_telemetry=False)
    )


def _get_or_create_collection(
        client: chromadb.PersistentClient,
) -> chromadb.Collection:
    """获取已有集合，不存在时新建（度量统一为 COSINE, 与 Milvus 后端一致）。

    与旧版"删除后重建"的行为不同，这里保留此前已上传文档的向量，
    以保证多文档问答可正常使用。
    """
    global _L2_SPACE_WARNED
    try:
        collection = client.get_collection(_COLLECTION)
        # 度量是建集合属性, 无法就地变更: 旧版默认建出的集合是 L2,
        # 与 Milvus 侧 COSINE 排序行为不一致——告警一次, 提示重建
        if not _L2_SPACE_WARNED:
            space = (collection.metadata or {}).get("hnsw:space", "l2")
            if space != "cosine":
                _L2_SPACE_WARNED = True
                LOGGER.warning(
                    f"ChromaDB 集合度量为 {space}（与 Milvus 侧 COSINE 不一致）: "
                    f"度量为建集合属性无法就地变更, 如需统一请停止服务后"
                    f"删除 .chroma_db 目录并重新上传文档"
                )
        return collection
    except Exception:
        pass
    return client.create_collection(
        _COLLECTION,
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
        chunks: List[Dict[str, Any]],
        file_path: str = "",
        doc_id: str = "",
) -> int:
    """向 ChromaDB 插入或更新分块向量。

    :param chunks: 分块字典列表，每个元素必须包含 ``content`` 与 ``vector``。
    :param file_path: 源文档路径（用于引用溯源）。
    :param doc_id: 文档唯一标识。
    :return: 已存储的分块数量。
    """
    if not chunks:
        return 0

    client = _get_client()
    collection = _get_or_create_collection(client)

    ids = [f"{doc_id}-chunk-{i:04d}" if doc_id else f"chunk-{i:04d}" for i, c in enumerate(chunks)]
    embeddings = [c.get("vector", []) for c in chunks]
    documents = [c.get("content", "") for c in chunks]

    file_name = Path(file_path).name if file_path else ""
    # created_at: 写入时刻时间戳, 供集合指纹感知"内容更新但分块数不变"的
    # 增量更新（与 Milvus 后端对齐, 见 get_collection_fingerprint）
    now = int(time.time())
    metadatas = [
        {
            "tokens": c.get("tokens", 0),
            "modality": c.get("modality", "text"),
            "order": c.get("chunk_order_index", i),
            "file_path": file_path,
            "file_name": file_name,
            "doc_id": doc_id,
            "created_at": now,
        }
        for i, c in enumerate(chunks)
    ]

    # 分批写入（与 Milvus 后端一致）: 规避大文档单次超大事务/payload
    batch_size = max(1, PROJECT_CONFIG.VECTOR_UPSERT_BATCH_SIZE)
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.upsert(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
    return len(ids)


def _query_collection(
        collection: Any,
        query_vectors: List[List[float]],
        top_k: int,
        where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """集合向量检索内部实现（可选元数据过滤）, 返回统一分块字典格式。"""
    query_kwargs: Dict[str, Any] = {
        "query_embeddings": query_vectors,
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_kwargs["where"] = where
    result = collection.query(**query_kwargs)
    # ChromaDB 返回嵌套列表 —— 展开批次维度
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    chunks: List[Dict[str, Any]] = []
    for i in range(len(ids)):
        meta = metas[i] if i < len(metas) else {}
        chunks.append(
            {
                "id": ids[i],
                "chunk_id": ids[i],
                "content": docs[i] if i < len(docs) else "",
                "file_path": meta.get("file_path", "unknown_source"),
                "file_name": meta.get("file_name", ""),
                "doc_id": meta.get("doc_id", ""),
                "tokens": meta.get("tokens", 0),
                "modality": meta.get("modality", "text"),
                "order": meta.get("order", i),
                "distance": distances[i] if i < len(distances) else None,
                # 写入时刻时间戳（upsert 时写入元数据; 存量历史记录无此键为 None）
                "created_at": meta.get("created_at"),
            }
        )
    return chunks


def query_chunks(
        query_vectors: List[List[float]], top_k: int = 60
) -> List[Dict[str, Any]]:
    """按向量相似度检索分块。

    返回兼容 LightRAG 格式的分块，元数据可用于引用 / 参考生成。

    :param query_vectors: 一个或多个查询向量。
    :param top_k: 返回的结果数量上限。
    :return: 分块字典列表，键包括：
        ``id``、``content``、``file_path``、``file_name``、``doc_id``、
        ``tokens``、``modality``、``order``、``distance``、``created_at``。
        集合不存在或为空时返回空列表。
    """
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        return _query_collection(collection, query_vectors, top_k)
    except Exception as e:
        LOGGER.error(f"ChromaDB 查询分块失败: {e}")
        return []


def query_chunks_by_doc(
        query_vectors: List[List[float]], doc_id: str, top_k: int = 8
) -> List[Dict[str, Any]]:
    """在指定文档范围内按向量相似度检索分块（文档级召回的定向注入通道）。

    返回格式与 query_chunks 完全一致。文档级召回命中某文档后, 用本函数
    定向取其 top 分块送入重排候选池——是否进最终窗口仍由重排阈值决定。
    """
    if not doc_id:
        return []
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        return _query_collection(
            collection, query_vectors, top_k, where={"doc_id": doc_id}
        )
    except Exception as e:
        LOGGER.error(f"ChromaDB 按文档查询分块失败: doc_id={doc_id}, {e}")
        return []


def delete_by_doc_id(doc_id: str) -> int:
    """删除指定文档的全部分块。

    :param doc_id: 待删除的文档标识。
    :return: 已删除的分块数量，操作失败时返回 -1。
    """
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        # 按元数据过滤删除: 先以 where 过滤只取 ID 列表（include=[]
        # 不加载正文/元数据）, 再按 ID 删除并得到删除数。
        # 原实现注释称"ChromaDB 不支持按元数据删除"而全表取出元数据
        # 线性扫描——实际 chroma 支持 where 过滤, 大集合下开销差两个量级
        def _matched_ids() -> List[str]:
            return collection.get(where={"doc_id": doc_id}, include=[]).get("ids", [])

        ids_to_delete = _matched_ids()
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            # 删除残留校验: 残留旧块会污染检索（增量更新"先删后写"依赖
            # 删除彻底）; 检出残留重试一次, 仍有则告警上报
            residue = _matched_ids()
            if residue:
                LOGGER.warning(
                    f"ChromaDB 删除后检出残留 {len(residue)} 块, 重试删除: doc_id={doc_id}"
                )
                collection.delete(ids=residue)
                residue = _matched_ids()
                if residue:
                    LOGGER.error(
                        f"ChromaDB 删除重试后仍有 {len(residue)} 块残留: doc_id={doc_id}"
                    )
        return len(ids_to_delete)
    except Exception as e:
        LOGGER.error(f"ChromaDB 删除文档分块失败: {e}")
        return -1


def get_all_chunks() -> List[Dict[str, Any]]:
    """返回集合中存储的全部分块。

    供 BM25 混合检索构建关键词索引使用。
    """
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        data = collection.get(include=["documents", "metadatas"])
        chunks: List[Dict[str, Any]] = []
        for i in range(len(data.get("ids", []))):
            meta = data["metadatas"][i] if i < len(data.get("metadatas", [])) else {}
            chunks.append({
                "id": data["ids"][i],
                "content": data["documents"][i] if i < len(data.get("documents", [])) else "",
                "file_path": meta.get("file_path", ""),
                "file_name": meta.get("file_name", ""),
                "doc_id": meta.get("doc_id", ""),
                "tokens": meta.get("tokens", 0),
                "modality": meta.get("modality", "text"),
                "order": meta.get("order", i),
            })
        return chunks
    except Exception as e:
        LOGGER.error(f"ChromaDB 获取全部分块失败: {e}")
        return []


def get_collection_fingerprint() -> str:
    """分块 ID 集合 + 最新写入时间指纹（md5）: 供 Web 侧判断 BM25 索引是否需要重建。

    指纹 = md5(最大 created_at + 排序后 ID 集)。**必须包含 created_at**:
    块 ID 为 <doc_id>-chunk-NNNN 顺序编号, 文档增量更新若分块数不变,
    ID 集合完全不变——仅 ID 指纹永远探测不到内容更新, BM25 索引将永久
    停留在旧版本（存量历史记录无 created_at 元数据, 以 0 参与计算,
    任一文档更新后即被新时间戳取代）。
    失败返回空串（Web 侧降级策略与 Milvus 路径一致）。
    """
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        data = collection.get(include=["metadatas"])
        ids = sorted(data.get("ids", []))
        metas = data.get("metadatas") or []
        max_created = max(
            (int((m or {}).get("created_at") or 0) for m in metas), default=0,
        )
        return hashlib.md5(f"{max_created}|{'|'.join(ids)}".encode()).hexdigest()
    except Exception as e:
        LOGGER.error(f"ChromaDB 计算集合指纹失败: {e}")
        return ""


def list_collection_doc_ids() -> Optional[set]:
    """集合中现存的全部 doc_id（孤儿分块 GC 用, 与文档表对账）。

    :return: doc_id 集合; 查询失败返回 None（GC 必须跳过本轮——
        空集合与查询失败不可混淆, 否则会把全部文档误判为孤儿）。
    """
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        data = collection.get(include=["metadatas"])
        doc_ids = set()
        for meta in data.get("metadatas") or []:
            doc_id = (meta or {}).get("doc_id") or ""
            if doc_id:
                doc_ids.add(doc_id)
        return doc_ids
    except Exception as e:
        LOGGER.error(f"ChromaDB 获取集合 doc_id 列表失败: {e}")
        return None


def get_collection_stats() -> Dict[str, Any]:
    """返回集合统计信息，用于监控。"""
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION)
        count = collection.count()
        return {"collection": _COLLECTION, "chunk_count": count, "status": "ok"}
    except Exception as e:
        LOGGER.error(f"ChromaDB 获取集合统计失败: {e}")
        return {"collection": _COLLECTION, "chunk_count": 0, "status": "empty"}
