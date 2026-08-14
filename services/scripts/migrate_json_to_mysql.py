# -*- coding: utf-8 -*-
"""一次性数据迁移: rag_storage JSON → MySQL。

迁移内容:
1. doc_status.json            → keenrobot_rag_document（文档表）
2. conversations.json         → keenrobot_rag_conversation +
                                keenrobot_rag_conversation_message（保留原会话 id）
3. retrieval_details.json     → keenrobot_rag_conversation_retrieval
   （旧版本内联在消息体 messages[].retrieval 中的检索详情一并迁入,
     独立文件条目优先, 与运行时迁移逻辑口径一致）
4. pipeline_state.json        → rag_pipeline_state（流水线启动时间, 单行）
   pipeline_history.jsonl     → rag_pipeline_history（历史消息, 保留原时分秒）

用法（项目根目录）:
    python services/scripts/migrate_json_to_mysql.py

幂等: 已存在的 job_id / 会话 id / 流水线状态与历史跳过, 可安全重复执行。
前提: .env 的 DATABASE_* 已配置且 MySQL 已通过应用启动建好表（aerich 迁移）。

注: 源文件目录固定为项目根下 rag_storage/（不再依赖配置项）; 迁移完成后
该目录即可整体删除, 本脚本对不存在的源文件一律安全跳过。
"""
import asyncio
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tortoise import Tortoise  # noqa: E402

from configure import LOGGER, PROJECT_CONFIG  # noqa: E402

_TIME_FMT = "%Y-%m-%d %H:%M:%S"
_TIME_ONLY_FMT = "%H:%M:%S"
STORAGE_DIR = PROJECT_ROOT / "rag_storage"
DOC_STATUS_FILE = STORAGE_DIR / "doc_status.json"
CONVERSATIONS_FILE = STORAGE_DIR / "conversations.json"
RETRIEVAL_DETAILS_FILE = STORAGE_DIR / "retrieval_details.json"
PIPELINE_STATE_FILE = STORAGE_DIR / "pipeline_state.json"
PIPELINE_HISTORY_FILE = STORAGE_DIR / "pipeline_history.jsonl"


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    """时间字符串 → datetime; 空/不可解析返回 None。"""
    if not value:
        return None
    try:
        return datetime.strptime(value, _TIME_FMT)
    except ValueError:
        return None


def _tortoise_config() -> Dict[str, Any]:
    return {
        "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
        "apps": {
            "models": {
                "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        LOGGER.warning(f"读取 {path} 失败, 跳过: {e}")
        return default


# ==================== 文档 ====================

# JSON 字段 → 模型字段（其余同名字段直接透传; 模型中已删除的字段自动跳过）
_DOC_FIELD_ALIASES = {
    "created_at": "created_time",
    "updated_at": "updated_time",
    "artifacts_dir": "artifacts_file",
}
_DOC_SKIP_FIELDS = {"id", "markdown"}  # id 由 job_id 表达; markdown 从不落库
_DOC_TIME_FIELDS = {
    "heartbeat_at", "parse_start_time", "parse_end_time",
    "term_start_time", "term_end_time", "analyze_start_time", "analyze_end_time",
    "chunk_start_time", "chunk_end_time", "embed_start_time", "embed_end_time",
    "process_end_time",
}


async def migrate_documents() -> int:
    from applications.jiayueyang.models.rag_document_model import RagDocument

    docs = _load_json(DOC_STATUS_FILE, {})
    if not docs:
        print(f"[文档] {DOC_STATUS_FILE.name} 不存在或为空, 跳过")
        return 0

    model_fields = set(RagDocument._meta.fields_map.keys()) - {"id"}
    migrated = skipped = 0
    for job_id, d in docs.items():
        if await RagDocument.filter(job_id=job_id).exists():
            skipped += 1
            continue
        values: Dict[str, Any] = {"job_id": job_id}
        for key, value in (d or {}).items():
            if key in _DOC_SKIP_FIELDS:
                continue
            field = _DOC_FIELD_ALIASES.get(key, key)
            if field not in model_fields:
                continue
            if field in _DOC_TIME_FIELDS or field in ("created_time", "updated_time"):
                value = _parse_time(value) if isinstance(value, str) else value
            values[field] = value
        obj = await RagDocument.create(**values)
        # created_time/updated_time 为 auto 字段, create 会被置为当前时间,
        # 用 queryset.update 回写历史时间（绕过 auto 逻辑）
        await RagDocument.filter(id=obj.id).update(
            created_time=_parse_time((d or {}).get("created_at")),
            updated_time=_parse_time((d or {}).get("updated_at")),
        )
        migrated += 1
        print(f"[文档] 已迁移: {job_id} ({(d or {}).get('filename')})")
    print(f"[文档] 迁移完成: 新增 {migrated} 条, 跳过已存在 {skipped} 条")
    return migrated


# ==================== 会话 / 消息 / 检索详情 ====================

async def migrate_conversations() -> int:
    from applications.jiayueyang.models.conversation_model import (
        MSG_DONE,
        RagConversation,
        RagConversationMessage,
        RagConversationRetrieval,
    )

    convs = _load_json(CONVERSATIONS_FILE, {})
    if not convs:
        print(f"[会话] {CONVERSATIONS_FILE.name} 不存在或为空, 跳过")
        return 0
    file_retrievals: Dict[str, Dict[str, Any]] = _load_json(RETRIEVAL_DETAILS_FILE, {})

    migrated = skipped = 0
    for conv_id_str, conv in convs.items():
        conv_id = int(conv_id_str)
        if await RagConversation.filter(id=conv_id).exists():
            skipped += 1
            continue

        created_time = _parse_time(conv.get("created_time"))
        updated_time = _parse_time(conv.get("updated_time")) or created_time
        obj = await RagConversation.create(
            id=conv_id,
            username=conv.get("username") or "User",
            title=(conv.get("title") or "新对话")[:255],
            pinned=bool(conv.get("pinned", False)),
            updated_time=updated_time,
        )
        # created_time 为 auto_now_add, 回写历史时间
        await RagConversation.filter(id=obj.id).update(created_time=created_time)

        messages = conv.get("messages", [])
        file_entries = file_retrievals.get(conv_id_str, {})
        for seq, m in enumerate(messages):
            m = m or {}
            await RagConversationMessage.create(
                conversation_id=conv_id,
                seq=seq,
                role=m.get("role") or "user",
                content=m.get("content") or "",
                status=m.get("status") or MSG_DONE,
                thinking_ms=m.get("thinking_ms"),
                created_time=_parse_time(m.get("created_time")),
            )
            # 检索详情: 独立文件条目优先; 其次旧版本内联在消息体的条目
            detail = file_entries.get(str(seq))
            if detail is None:
                detail = m.get("retrieval")
            if detail is not None:
                await RagConversationRetrieval.create(
                    conversation_id=conv_id, message_seq=seq, detail=detail,
                )

        migrated += 1
        print(f"[会话] 已迁移: id={conv_id} ({obj.title}, {len(messages)} 条消息)")
    print(f"[会话] 迁移完成: 新增 {migrated} 个会话, 跳过已存在 {skipped} 个")
    return migrated


# ==================== 流水线状态 / 历史 ====================

async def migrate_pipeline() -> int:
    from applications.jiayueyang.models.pipeline_model import (
        RagPipelineHistory,
        RagPipelineState,
    )

    # 运行状态（单行）: start_time（"%Y-%m-%d %H:%M:%S" 字符串, 可为 null）
    if await RagPipelineState.all().exists():
        print("[流水线] rag_pipeline_state 已有数据, 跳过状态迁移")
    else:
        state = _load_json(PIPELINE_STATE_FILE, {})
        start_time = _parse_time((state or {}).get("start_time"))
        await RagPipelineState.create(start_time=start_time)
        print(f"[流水线] 已迁移运行状态: start_time={start_time}")

    # 历史消息（JSONL, 每行 {"t": "HH:MM:SS", "m": "..."}）
    if await RagPipelineHistory.all().exists():
        print("[流水线] rag_pipeline_history 已有数据, 跳过历史迁移")
        return 0
    if not PIPELINE_HISTORY_FILE.exists():
        print(f"[流水线] {PIPELINE_HISTORY_FILE.name} 不存在, 跳过历史迁移")
        return 0

    # 原记录仅时分秒（无日期）, 以迁移执行日补全日期; 先后顺序由自增 id 保证
    base_date = datetime.now().date()
    migrated = 0
    with PIPELINE_HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                t = datetime.strptime(item.get("t", ""), _TIME_ONLY_FMT).time()
                created = datetime.combine(base_date, t)
            except ValueError:
                created = datetime.now()
            await RagPipelineHistory.create(message=item.get("m", ""), created_time=created)
            migrated += 1
    print(f"[流水线] 已迁移 {migrated} 条历史消息")
    return migrated


async def main() -> None:
    await Tortoise.init(config=_tortoise_config())
    try:
        await migrate_documents()
        await migrate_conversations()
        await migrate_pipeline()
        print("全部迁移完成。JSON 源文件保持原样未动（可人工核对后再归档）。")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        LOGGER.error(f"数据迁移失败: {e}\n{traceback.format_exc()}")
        sys.exit(1)
