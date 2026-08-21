# -*- coding: utf-8 -*-
"""Milvus 持久化向量存储，接口设计参考 LightRAG

vector_store.py（ChromaDB）的直接替换实现，对外暴露同名的 4 个公共函数。
"""

import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# 尝试导入 pymilvus；milvus 后端为可选依赖，仅在使用该后端时需要安装
try:
    from pymilvus import (  # type: ignore
        CollectionSchema,
        DataType,
        FieldSchema,
        MilvusClient,
    )
    _HAS_PYMILVUS = True
except ImportError:
    _HAS_PYMILVUS = False
    MilvusClient = None  # type: ignore

from configure import LOGGER, PROJECT_CONFIG

# ---------------------------------------------------------------------------
# milvus-lite Windows 兼容补丁
# ---------------------------------------------------------------------------

def _patch_milvus_lite_windows_rename() -> None:
    """修复 milvus-lite 在 Windows 上 manifest 保存必然失败的问题。

    milvus_lite/storage/manifest.py 的 Manifest.save() 走"写 .tmp →
    os.rename(tmp, target)": POSIX 的 rename 会原子覆盖已存在的目标,
    而 Windows 上目标存在时抛 FileExistsError([WinError 183])。持久化
    的 .milvus.db 中 manifest.json 必然已存在（上一次会话所建）, 于是
    任何触发 manifest 保存的 flush（大批量 upsert/delete）都会失败——
    小文档因不触发中途 flush 而侥幸躲过, 大文档必中。

    修复: 把该模块命名空间内的 os 替换为代理, 仅将 rename 重定向到
    覆盖语义的 os.replace（POSIX 上 os.replace 与 os.rename 完全等价,
    Linux 部署零行为变化）, 其余属性原样委托, 不影响其他模块。
    幂等: 重复导入/调用只打一次补丁。
    """
    if os.name != "nt":
        return
    try:
        from milvus_lite.storage import manifest as _manifest_mod
    except ImportError:
        return  # 未安装 milvus-lite（独立服务端模式）时无需补丁
    if getattr(_manifest_mod, "_win_rename_patched", False):
        return

    class _OsReplaceRename:
        """os 模块代理: 仅 rename 重定向为 os.replace, 其余委托真实 os。"""

        def __init__(self, real_os):
            self._real = real_os

        def rename(self, src, dst):
            return os.replace(src, dst)

        def __getattr__(self, name):
            return getattr(self._real, name)

    _manifest_mod.os = _OsReplaceRename(os)
    _manifest_mod._win_rename_patched = True
    LOGGER.info("已补丁 milvus-lite manifest.save 的 Windows 不兼容（rename → replace）")


# 模块导入即打补丁（本模块仅在 milvus 后端被导入, 先于任何 Milvus 操作）
_patch_milvus_lite_windows_rename()


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_COLLECTION_NAME = "rag_chunks"

# Milvus Lite 单进程锁冲突的退避重试参数
_LOCK_RETRY_TIMES = 5
_LOCK_RETRY_INTERVAL = 1.0

# VARCHAR 最大字节长度（Milvus 上限为 65535 字节）
_MAX_CONTENT_BYTES = 65535
_MAX_FILE_PATH_BYTES = 1024
_MAX_FILE_NAME_BYTES = 512
_MAX_DOC_ID_BYTES = 256
_MAX_MODALITY_BYTES = 64

# ---------------------------------------------------------------------------
# 客户端管理（每次操作短连接）
# ---------------------------------------------------------------------------
_collection_ready: bool = False


@contextmanager
def _milvus_client() -> Iterator[MilvusClient]:  # type: ignore
    """按操作创建短连接, 用完即关闭（接口设计参考 LightRAG）。

    Milvus Lite 为单进程嵌入式数据库, 同一时刻仅允许一个进程打开数据目录。
    采用"每操作短连接"策略及时释放文件锁, 并对瞬时锁冲突做退避重试,
    以容纳 Web 与 Celery Worker 之间的短暂操作重叠。
    （MILVUS_URI 指向独立 Milvus 服务端时不受上述限制。）
    """
    if not _HAS_PYMILVUS:
        raise ImportError(
            "pymilvus 未安装, 请执行: pip install pymilvus>=2.6.2"
        )

    # 配置 gRPC 保活，避免 Milvus Lite 返回 "too_many_pings" GOAWAY。
    # 默认 20 秒；提高到 120 秒可避免被服务端限流。
    import os as _os
    _os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "120000")
    _os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "30000")
    _os.environ.setdefault("GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS", "1")
    _os.environ.setdefault("GRPC_ARG_HTTP2_MIN_RECV_PING_INTERVAL_WITHOUT_DATA_MS", "60000")

    kwargs: Dict[str, Any] = {"uri": PROJECT_CONFIG.MILVUS_URI}
    if PROJECT_CONFIG.MILVUS_USER:
        kwargs["user"] = PROJECT_CONFIG.MILVUS_USER
    if PROJECT_CONFIG.MILVUS_PASSWORD:
        kwargs["password"] = PROJECT_CONFIG.MILVUS_PASSWORD
    if PROJECT_CONFIG.MILVUS_TOKEN:
        kwargs["token"] = PROJECT_CONFIG.MILVUS_TOKEN

    # 瞬时锁冲突退避重试（另一进程正在操作 Milvus Lite 数据目录）
    last_error: Optional[Exception] = None
    for attempt in range(_LOCK_RETRY_TIMES):
        try:
            client = MilvusClient(**kwargs)
            break
        except Exception as e:
            last_error = e
            if attempt < _LOCK_RETRY_TIMES - 1:
                LOGGER.warning(f"Milvus 连接被占用, 第 {attempt + 1} 次重试: {e}")
                time.sleep(_LOCK_RETRY_INTERVAL)
    else:
        raise RuntimeError(f"Milvus 连接失败（已重试 {_LOCK_RETRY_TIMES} 次）: {last_error}")

    try:
        yield client
    finally:
        try:
            client.close()
        except Exception:
            pass


def _ensure_collection(client: MilvusClient) -> None:  # type: ignore
    """集合与索引不存在时创建，随后加载（接口设计参考 LightRAG）。"""
    global _collection_ready
    if _collection_ready:
        # 短连接模式下每个新客户端（Milvus Lite 每次启动独立实例）重新加载集合
        try:
            client.load_collection(_COLLECTION_NAME)
        except Exception:
            pass
        return

    if client.has_collection(_COLLECTION_NAME):
        _verify_collection_dim(client)
        client.load_collection(_COLLECTION_NAME)
        _collection_ready = True
        return

    # 创建 schema
    schema = CollectionSchema(
        fields=[
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                max_length=256,
                is_primary=True,
            ),
            FieldSchema(
                name="vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=PROJECT_CONFIG.EMBEDDING_DIM,
            ),
            FieldSchema(
                name="created_at",
                dtype=DataType.INT64,
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=_MAX_CONTENT_BYTES,
            ),
            FieldSchema(
                name="file_path",
                dtype=DataType.VARCHAR,
                max_length=_MAX_FILE_PATH_BYTES,
            ),
            FieldSchema(
                name="file_name",
                dtype=DataType.VARCHAR,
                max_length=_MAX_FILE_NAME_BYTES,
            ),
            FieldSchema(
                name="doc_id",
                dtype=DataType.VARCHAR,
                max_length=_MAX_DOC_ID_BYTES,
            ),
            FieldSchema(
                name="tokens",
                dtype=DataType.INT64,
            ),
            FieldSchema(
                name="modality",
                dtype=DataType.VARCHAR,
                max_length=_MAX_MODALITY_BYTES,
            ),
            FieldSchema(
                name="chunk_order_index",
                dtype=DataType.INT64,
            ),
        ],
        enable_dynamic_field=True,
    )

    try:
        client.create_collection(collection_name=_COLLECTION_NAME, schema=schema)
    except Exception as create_err:
        # Milvus Lite 可能丢失元数据（has_collection 返回 False），
        # 而操作系统层面的集合目录仍然存在 → 仅此一种场景删除后重建。
        #
        # ⚠️ 原实现对 create_collection 的任何异常都 rmtree 集合目录——
        # 该目录存放的是全部文档的向量, 并发竞争/权限/磁盘等偶发失败
        # 会静默删库。收窄后的判定:
        # 1) has_collection 为 True → 并发竞争（另一进程刚建好）, 直接
        #    加载即可, 绝不动磁盘;
        # 2) has_collection 为 False 且本地残留目录存在 → 元数据丢失,
        #    目录中的向量本就已不可达, 删除重建;
        # 3) 其他情形（含服务端模式无本地目录）→ 原样上抛。建集合失败
        #    只会让当前文档 failed（可重试）, 绝不破坏存量数据。
        if client.has_collection(_COLLECTION_NAME):
            LOGGER.info(f"集合已由其他进程创建, 直接加载: {create_err}")
            client.load_collection(_COLLECTION_NAME)
            _collection_ready = True
            return

        stale_dir = _stale_collection_dir()
        if stale_dir is None or not stale_dir.exists():
            raise

        LOGGER.error(
            f"检测到集合元数据丢失且残留目录存在 ({stale_dir}), "
            f"删除残留后重建: {type(create_err).__name__}: {create_err}"
        )
        import shutil
        shutil.rmtree(str(stale_dir), ignore_errors=True)
        client.create_collection(collection_name=_COLLECTION_NAME, schema=schema)

    # 创建向量索引
    from pymilvus.milvus_client.index import IndexParams

    _v_idx = IndexParams()
    _v_idx.add_index(
        field_name="vector", index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    client.create_index(collection_name=_COLLECTION_NAME, index_params=_v_idx)

    # 为 doc_id 创建标量索引，加速按文档删除
    try:
        _s_idx = IndexParams()
        _s_idx.add_index(field_name="doc_id", index_type="INVERTED")
        client.create_index(collection_name=_COLLECTION_NAME, index_params=_s_idx)
    except Exception:
        pass  # 标量索引仅为性能优化，并非必需

    client.load_collection(_COLLECTION_NAME)
    _collection_ready = True


# ---------------------------------------------------------------------------
# 截断保护
# ---------------------------------------------------------------------------
def _verify_collection_dim(client: MilvusClient) -> None:  # type: ignore
    """校验已有集合的向量维度与 ``EMBEDDING_DIM`` 配置一致。

    维度不一致（更换嵌入模型 / 改过配置）会使后续全部 upsert 失败——
    前置校验把"流水线最后一步才失败"变成秒级失败。仅在进程内首次
    确认集合存在时调用一次（_collection_ready 置位后不再进入本分支）。

    pymilvus 各版本 describe 返回结构略有差异: 解析不出维度时跳过
    校验（upsert 时仍会自然报错）, 校验本身不阻塞主流程。
    """
    try:
        desc = client.describe_collection(_COLLECTION_NAME)
        for field in desc.get("fields", []):
            if field.get("name") != "vector":
                continue
            dim = field.get("dim") or (field.get("params") or {}).get("dim")
            if dim is not None and int(dim) != PROJECT_CONFIG.EMBEDDING_DIM:
                raise RuntimeError(
                    f"向量库集合维度 ({dim}) 与配置 EMBEDDING_DIM "
                    f"({PROJECT_CONFIG.EMBEDDING_DIM}) 不一致: 通常因更换嵌入模型"
                    f"或修改维度配置而未重建集合。请修正配置与集合一致, "
                    f"或清空集合后重新上传全部文档"
                )
            return
    except RuntimeError:
        raise  # 维度不一致是确定性配置错误, 必须上抛
    except Exception as e:
        LOGGER.debug(f"集合维度校验跳过（describe 未取到维度信息）: {e}")


def _stale_collection_dir() -> Optional[Path]:
    """解析 Milvus Lite 集合在磁盘上的目录; 服务端模式（非 file URI）无本地目录, 返回 None。"""
    if not PROJECT_CONFIG.MILVUS_URI.startswith("file"):
        return None
    db_dir = Path(
        PROJECT_CONFIG.MILVUS_URI.replace("file://", "").replace("file:", "")
    )
    return db_dir / "collections" / _COLLECTION_NAME


def _truncate_bytes(value: str, max_bytes: int) -> str:
    """将字符串截断到 *max_bytes* 个 UTF-8 字节以内。"""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    # 逐字节回退，直到落在合法的 UTF-8 边界上
    while max_bytes > 0:
        try:
            return encoded[:max_bytes].decode("utf-8")
        except UnicodeDecodeError:
            max_bytes -= 1
    return ""


# ---------------------------------------------------------------------------
# 公共 API —— 与 vector_store.py 签名完全一致（同名同参的直接替换）
# ---------------------------------------------------------------------------

def upsert_chunks(
        chunks: List[Dict[str, Any]],
        file_path: str = "",
        doc_id: str = "",
) -> int:
    """向 Milvus 插入或更新分块向量（接口设计参考 LightRAG）。

    :param chunks: 分块字典列表，每个元素必须包含 ``content`` 与 ``vector``。
    :param file_path: 源文档路径（用于引用溯源）。
    :param doc_id: 文档唯一标识。
    :return: 已存储的分块数量。
    """
    if not chunks:
        return 0

    file_name = Path(file_path).name if file_path else ""
    now = int(time.time())

    records: List[Dict[str, Any]] = []
    for i, c in enumerate(chunks):
        chunk_id = f"{doc_id}-chunk-{i:04d}" if doc_id else f"chunk-{i:04d}"
        vec = c.get("vector", [])
        content = c.get("content", "")
        records.append({
            "id": chunk_id,
            "vector": vec,
            "created_at": now,
            "content": _truncate_bytes(content, _MAX_CONTENT_BYTES),
            "file_path": _truncate_bytes(file_path, _MAX_FILE_PATH_BYTES),
            "file_name": _truncate_bytes(file_name, _MAX_FILE_NAME_BYTES),
            "doc_id": _truncate_bytes(doc_id, _MAX_DOC_ID_BYTES),
            "tokens": c.get("tokens", 0),
            "modality": _truncate_bytes(
                c.get("modality", "text"), _MAX_MODALITY_BYTES
            ),
            "chunk_order_index": c.get("chunk_order_index", i),
        })

    with _milvus_client() as client:
        _ensure_collection(client)
        # 分批写入: 数千分块 × 1024 维一次性 upsert 的 payload 可达数十 MB,
        # 可能触及 gRPC 消息上限导致整篇文档在流水线最后一步失败。
        # 块 ID 幂等, 某批失败后由管道标 failed, 重试整篇写入安全
        batch_size = max(1, PROJECT_CONFIG.VECTOR_UPSERT_BATCH_SIZE)
        for start in range(0, len(records), batch_size):
            client.upsert(
                collection_name=_COLLECTION_NAME,
                data=records[start:start + batch_size],
            )
    return len(records)


def _search_chunks(
        client: Any,
        query_vectors: List[List[float]],
        top_k: int,
        filter_expr: str = "",
) -> List[Dict[str, Any]]:
    """向量检索内部实现（可选标量过滤）, 返回统一分块字典格式。"""
    _ensure_collection(client)

    output_fields = [
        "id", "content", "file_path", "file_name",
        "doc_id", "tokens", "modality", "chunk_order_index",
        "created_at",
    ]

    search_kwargs: Dict[str, Any] = {
        "collection_name": _COLLECTION_NAME,
        "data": query_vectors,  # Milvus 期望传入向量列表; 单个查询向量也需包装成列表
        "limit": top_k,
        "output_fields": output_fields,
        "search_params": {"metric_type": "COSINE"},
    }
    if filter_expr:
        search_kwargs["filter"] = filter_expr
    results = client.search(**search_kwargs)

    # Milvus 返回 list[SearchResult]；展开第一个查询的结果
    if not results:
        return []

    hits = results[0]
    chunks: List[Dict[str, Any]] = []
    for hit in hits:
        entity = hit.get("entity", {})
        chunks.append({
            "id": hit["id"],
            "chunk_id": hit["id"],
            "content": entity.get("content", ""),
            "file_path": entity.get("file_path", "unknown_source"),
            "file_name": entity.get("file_name", ""),
            "doc_id": entity.get("doc_id", ""),
            "tokens": entity.get("tokens", 0),
            "modality": entity.get("modality", "text"),
            "order": entity.get("chunk_order_index", 0),
            "distance": hit.get("distance", None),
            "created_at": entity.get("created_at"),
        })
    return chunks


def query_chunks(
        query_vectors: List[List[float]], top_k: int = 60
) -> List[Dict[str, Any]]:
    """按向量相似度从 Milvus 检索分块（接口设计参考 LightRAG）。

    :param query_vectors: 一个或多个查询向量。
    :param top_k: 返回的结果数量上限。
    :return: 分块字典列表，键与 ChromaDB 版本完全一致：
        ``id``、``chunk_id``、``content``、``file_path``、``file_name``、``doc_id``、
        ``tokens``、``modality``、``order``、``distance``、``created_at``。
    """
    try:
        with _milvus_client() as client:
            return _search_chunks(client, query_vectors, top_k)
    except Exception as e:
        LOGGER.error(f"Milvus 查询分块失败: {e}")
        return []


def query_chunks_by_doc(
        query_vectors: List[List[float]], doc_id: str, top_k: int = 8
) -> List[Dict[str, Any]]:
    """在指定文档范围内按向量相似度检索分块（文档级召回的定向注入通道）。

    以标量过滤限定 doc_id（doc_id 上有倒排索引, 过滤开销可忽略）,
    返回格式与 query_chunks 完全一致。文档级召回命中某文档后, 用本函数
    定向取其 top 分块送入重排候选池——是否进最终窗口仍由重排阈值决定。
    """
    if not doc_id:
        return []
    try:
        with _milvus_client() as client:
            return _search_chunks(
                client, query_vectors, top_k, filter_expr=f'doc_id == "{doc_id}"'
            )
    except Exception as e:
        LOGGER.error(f"Milvus 按文档查询分块失败: doc_id={doc_id}, {e}")
        return []


def delete_by_doc_id(doc_id: str) -> int:
    """删除指定文档的全部分块（接口设计参考 LightRAG, 含删除残留校验）。

    :param doc_id: 待删除的文档标识。
    :return: 已删除的分块数量，操作失败时返回 -1。
    """
    try:
        with _milvus_client() as client:
            _ensure_collection(client)

            def _query_pks() -> List[str]:
                rows = client.query(
                    collection_name=_COLLECTION_NAME,
                    filter=f'doc_id == "{doc_id}"',
                    output_fields=["id"],
                )
                return [r["id"] for r in rows]

            # 按 doc_id 过滤查询
            pks = _query_pks()
            if pks:
                client.delete(collection_name=_COLLECTION_NAME, pks=pks)
                # 删除残留校验: 残留旧块会污染检索（增量更新"先删后写"依赖
                # 删除彻底）; 检出残留重试一次, 仍有则告警上报
                residue = _query_pks()
                if residue:
                    LOGGER.warning(
                        f"Milvus 删除后检出残留 {len(residue)} 块, 重试删除: doc_id={doc_id}"
                    )
                    client.delete(collection_name=_COLLECTION_NAME, pks=residue)
                    residue = _query_pks()
                    if residue:
                        LOGGER.error(
                            f"Milvus 删除重试后仍有 {len(residue)} 块残留: doc_id={doc_id}"
                        )
            return len(pks)
    except Exception as e:
        LOGGER.error(f"Milvus 删除文档分块失败: {e}")
        return -1


def get_all_chunks() -> List[Dict[str, Any]]:
    """返回 Milvus 集合中存储的全部分块，供 BM25 建索引使用。"""
    try:
        with _milvus_client() as client:
            _ensure_collection(client)
            results = client.query(
                collection_name=_COLLECTION_NAME,
                filter="id != ''",
                output_fields=["id", "content", "file_path", "file_name", "doc_id", "tokens", "modality", "chunk_order_index"],
                limit=100000,
            )
        # 静默上限告警: 触顶说明 BM25 索引基于不完整数据, 必须可见
        if len(results) >= 100000:
            LOGGER.warning(
                "Milvus get_all_chunks 触及单次查询上限 100000: "
                "BM25 关键词索引可能不完整, 请关注分块总量增长"
            )
        return [
            {
                "id": r.get("id", ""),
                "content": r.get("content", ""),
                "file_path": r.get("file_path", ""),
                "file_name": r.get("file_name", ""),
                "doc_id": r.get("doc_id", ""),
                "tokens": r.get("tokens", 0),
                "modality": r.get("modality", "text"),
                "order": r.get("chunk_order_index", 0),
                "content_headings": r.get("content_headings", ""),
            }
            for r in results
        ]
    except Exception as e:
        LOGGER.error(f"Milvus 获取全部分块失败: {e}")
        return []


def get_collection_fingerprint() -> str:
    """分块 ID 集合 + 最新写入时间指纹（md5）: 供 Web 侧判断 BM25 索引是否需要重建。

    在 Worker 进程内计算（只查 ID 与 created_at 两列的轻量查询）, RPC 路径
    仅回传一个短字符串——替代原方案中"Web 每次查询都全量拉取全部分块正文
    来算指纹"的做法（稳态下每次查询的跨进程 payload 从数十 MB 降到字节级）。

    指纹 = md5(最大 created_at + 排序后 ID 集)。**必须包含 created_at**:
    块 ID 为 <doc_id>-chunk-NNNN 顺序编号, 文档增量更新若分块数不变,
    ID 集合完全不变——仅 ID 指纹永远探测不到内容更新, BM25 索引将永久
    停留在旧版本; 而 upsert 每次写入都刷新 created_at, 以其最大值入指纹
    即可感知任何一次重写。

    失败返回空串: Web 侧据此降级（有旧索引用旧索引, 冷启动则全量拉取）。
    """
    try:
        with _milvus_client() as client:
            _ensure_collection(client)
            results = client.query(
                collection_name=_COLLECTION_NAME,
                filter="id != ''",
                output_fields=["id", "created_at"],
                limit=100000,
            )
        ids = sorted(r.get("id", "") for r in results)
        if len(ids) >= 100000:
            LOGGER.warning(
                "Milvus 指纹计算触及单次查询上限 100000: 指纹可能不稳定"
            )
        max_created = max((int(r.get("created_at") or 0) for r in results), default=0)
        return hashlib.md5(f"{max_created}|{'|'.join(ids)}".encode()).hexdigest()
    except Exception as e:
        LOGGER.error(f"Milvus 计算集合指纹失败: {e}")
        return ""


def list_collection_doc_ids() -> Optional[set]:
    """集合中现存的全部 doc_id（孤儿分块 GC 用, 与文档表对账）。

    :return: doc_id 集合; 查询失败返回 None（GC 必须跳过本轮——
        空集合与查询失败不可混淆, 否则会把全部文档误判为孤儿）。
    """
    try:
        with _milvus_client() as client:
            _ensure_collection(client)
            results = client.query(
                collection_name=_COLLECTION_NAME,
                filter="id != ''",
                output_fields=["doc_id"],
                limit=100000,
            )
        return {r.get("doc_id", "") for r in results if r.get("doc_id")}
    except Exception as e:
        LOGGER.error(f"Milvus 获取集合 doc_id 列表失败: {e}")
        return None


def get_collection_stats() -> Dict[str, Any]:
    """返回集合统计信息，用于监控。"""
    try:
        with _milvus_client() as client:
            _ensure_collection(client)
            stats = client.get_collection_stats(_COLLECTION_NAME)
        row_count = stats.get("row_count", 0) if isinstance(stats, dict) else 0
        return {
            "collection": _COLLECTION_NAME,
            "chunk_count": row_count,
            "status": "ok",
            "backend": "milvus",
        }
    except Exception as e:
        LOGGER.error(f"Milvus 获取集合统计失败: {e}")
        return {
            "collection": _COLLECTION_NAME,
            "chunk_count": 0,
            "status": "empty",
            "backend": "milvus",
        }


# ---------------------------------------------------------------------------
# 对话记忆集合（L4 向量回忆）——与文档分块集合 rag_chunks 相互独立
# ---------------------------------------------------------------------------
# 设计: 每个"问答轮次"一条向量, 以 conversation_id 隔离, 问答时按当前问题
# 召回本会话的旧轮次, 为超长对话提供精准的细节回忆。集合、维度与文档分块
# 共用 EMBEDDING_DIM（同一嵌入模型）。
_MEMORY_COLLECTION_NAME = "rag_chat_memory"

# VARCHAR 字节上限（Milvus 上限 65535, 预留余量）
_MEMORY_MAX_QUESTION_BYTES = 8192
_MEMORY_MAX_ANSWER_BYTES = 16384
_MEMORY_MAX_CONV_ID_BYTES = 64

_memory_collection_ready: bool = False


def _ensure_memory_collection(client: MilvusClient) -> None:  # type: ignore
    """对话记忆集合与索引不存在时创建, 随后加载。"""
    global _memory_collection_ready
    if _memory_collection_ready:
        try:
            client.load_collection(_MEMORY_COLLECTION_NAME)
        except Exception:
            pass
        return

    if client.has_collection(_MEMORY_COLLECTION_NAME):
        client.load_collection(_MEMORY_COLLECTION_NAME)
        _memory_collection_ready = True
        return

    schema = CollectionSchema(
        fields=[
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=PROJECT_CONFIG.EMBEDDING_DIM),
            FieldSchema(name="conversation_id", dtype=DataType.VARCHAR, max_length=_MEMORY_MAX_CONV_ID_BYTES),
            FieldSchema(name="seq", dtype=DataType.INT64),
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=_MEMORY_MAX_QUESTION_BYTES),
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=_MEMORY_MAX_ANSWER_BYTES),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ],
        enable_dynamic_field=True,
    )

    try:
        client.create_collection(collection_name=_MEMORY_COLLECTION_NAME, schema=schema)
    except Exception as create_err:
        # 并发竞争（另一进程刚建好）→ 直接加载; 其余情形上抛
        if client.has_collection(_MEMORY_COLLECTION_NAME):
            LOGGER.info(f"对话记忆集合已由其他进程创建, 直接加载: {create_err}")
            client.load_collection(_MEMORY_COLLECTION_NAME)
            _memory_collection_ready = True
            return
        raise

    from pymilvus.milvus_client.index import IndexParams

    _v_idx = IndexParams()
    _v_idx.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_index(collection_name=_MEMORY_COLLECTION_NAME, index_params=_v_idx)

    # conversation_id 标量索引: 加速按会话过滤召回与整会话删除
    try:
        _s_idx = IndexParams()
        _s_idx.add_index(field_name="conversation_id", index_type="INVERTED")
        client.create_index(collection_name=_MEMORY_COLLECTION_NAME, index_params=_s_idx)
    except Exception:
        pass  # 标量索引仅为性能优化

    client.load_collection(_MEMORY_COLLECTION_NAME)
    _memory_collection_ready = True


def upsert_chat_memory(records: List[Dict[str, Any]]) -> int:
    """写入/更新对话轮次记忆向量。

    :param records: 每条须含 id/vector/conversation_id/seq/question/answer。
    :return: 已写入条数。
    """
    if not records:
        return 0
    now = int(time.time())
    rows: List[Dict[str, Any]] = []
    for r in records:
        rows.append({
            "id": r["id"],
            "vector": r.get("vector", []),
            "conversation_id": _truncate_bytes(str(r.get("conversation_id", "")), _MEMORY_MAX_CONV_ID_BYTES),
            "seq": int(r.get("seq", 0)),
            "question": _truncate_bytes(r.get("question", ""), _MEMORY_MAX_QUESTION_BYTES),
            "answer": _truncate_bytes(r.get("answer", ""), _MEMORY_MAX_ANSWER_BYTES),
            "created_at": now,
        })
    with _milvus_client() as client:
        _ensure_memory_collection(client)
        client.upsert(collection_name=_MEMORY_COLLECTION_NAME, data=rows)
    return len(rows)


def search_chat_memory(
        query_vectors: List[List[float]],
        conversation_id: str,
        top_k: int = 3,
        max_seq: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """按向量相似度召回指定会话的旧轮次记忆。

    :param query_vectors: 查询向量列表。
    :param conversation_id: 仅召回该会话的记忆。
    :param top_k: 返回条数上限。
    :param max_seq: 仅召回 seq <= max_seq 的轮次（用于排除近期窗口内轮次）。
    :return: 轮次字典列表（question/answer/seq/distance）。
    """
    try:
        with _milvus_client() as client:
            _ensure_memory_collection(client)
            filter_expr = f'conversation_id == "{conversation_id}"'
            if max_seq is not None:
                filter_expr += f" and seq <= {int(max_seq)}"
            results = client.search(
                collection_name=_MEMORY_COLLECTION_NAME,
                data=query_vectors,
                limit=top_k,
                filter=filter_expr,
                output_fields=["question", "answer", "seq", "conversation_id"],
                search_params={"metric_type": "COSINE"},
            )
            if not results:
                return []
            hits = results[0]
            turns: List[Dict[str, Any]] = []
            for hit in hits:
                entity = hit.get("entity", {})
                turns.append({
                    "question": entity.get("question", ""),
                    "answer": entity.get("answer", ""),
                    "seq": entity.get("seq", 0),
                    "distance": hit.get("distance", None),
                })
            return turns
    except Exception as e:
        LOGGER.error(f"Milvus 召回对话记忆失败: {e}")
        return []


def delete_chat_memory_by_conv(conversation_id: str) -> int:
    """删除指定会话的全部对话记忆向量。

    :return: 已删除条数, 失败返回 -1。
    """
    try:
        with _milvus_client() as client:
            _ensure_memory_collection(client)
            results = client.query(
                collection_name=_MEMORY_COLLECTION_NAME,
                filter=f'conversation_id == "{conversation_id}"',
                output_fields=["id"],
            )
            pks = [r["id"] for r in results]
            if pks:
                client.delete(collection_name=_MEMORY_COLLECTION_NAME, pks=pks)
            return len(pks)
    except Exception as e:
        LOGGER.error(f"Milvus 删除对话记忆失败: {e}")
        return -1
