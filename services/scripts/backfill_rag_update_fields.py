# -*- coding: utf-8 -*-
"""一次性回填: 为存量文档补齐增量更新所需的两类数据。

v0.1x 引入文档增量更新后, 新上传/更新的文档会记录源文件 SHA256
（``rag_document.file_sha256``）并随嵌入落盘 ``embeddings_meta.json``
（嵌入模型名 + 维度, 向量复用的模型漂移守卫）。存量文档缺少这两项:

1. ``file_sha256``: 从留档源文件（input/<job_id>/）读取字节计算回填。
   缺失时增量更新的"文件未变化"快速通道不生效（不影响正确性,
   仅首次更新必然重处理）;
2. ``embeddings_meta.json``: 为已有 embeddings.json 的产物目录补写。
   **注意前提假设**: 存量向量确系当前 .env 配置的 EMBEDDING_MODEL /
   EMBEDDING_DIM 所嵌入。若曾经更换过嵌入模型而未重建向量库, 请勿
   执行本脚本（应先重新上传全部文档）——错误的 meta 会使增量更新
   复用旧模型的向量, 造成跨模型相似度失真。

用法（项目根目录）:
    python services/scripts/backfill_rag_update_fields.py

幂等: 已有哈希/meta 的文档跳过, 可安全重复执行。
前提: .env 的 DATABASE_* 已配置。
"""
import asyncio
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tortoise import Tortoise  # noqa: E402

from configure import LOGGER, PROJECT_CONFIG  # noqa: E402


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


def _sha256_of_file(path: Path) -> str:
    """分块读取计算文件 SHA256（200MB 大文件不整块驻留内存）。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(8 * 1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


async def backfill() -> None:
    from applications.jiayueyang.models.rag_document_model import RagDocument

    docs = await RagDocument.all()
    if not docs:
        print("没有文档记录, 无需回填。")
        return

    meta_payload = json.dumps(
        {
            "model": PROJECT_CONFIG.EMBEDDING_MODEL,
            "dim": PROJECT_CONFIG.EMBEDDING_DIM,
            "created_at": int(time.time()),
            "backfilled": True,
        },
        ensure_ascii=False,
    )

    hashed = hash_skipped = meta_written = meta_skipped = 0
    for d in docs:
        # ---- 1) file_sha256 回填（任何状态均可, 只要留档源文件存在）----
        if not d.file_sha256:
            input_path = Path(d.input_path or "")
            if input_path.is_file():
                try:
                    sha = await asyncio.to_thread(_sha256_of_file, input_path)
                    await RagDocument.filter(job_id=d.job_id).update(file_sha256=sha)
                    hashed += 1
                    print(f"[哈希] 已回填: {d.filename} ({sha[:12]}…)")
                except OSError as e:
                    print(f"[哈希] 读取失败, 跳过: {d.filename} — {e}")
            else:
                hash_skipped += 1
                print(f"[哈希] 跳过（源文件未留档）: {d.filename}")
        else:
            hash_skipped += 1

        # ---- 2) embeddings_meta.json 回填（仅 complete 且有向量产物）----
        if d.status != "complete":
            continue
        bundle_dir = Path(d.output_path or "")
        emb_file = bundle_dir / "embeddings.json"
        meta_file = bundle_dir / "embeddings_meta.json"
        if not emb_file.is_file():
            continue
        if meta_file.is_file():
            meta_skipped += 1
            continue
        try:
            meta_file.write_text(meta_payload, encoding="utf-8")
            meta_written += 1
            print(f"[meta] 已写入: {d.filename}")
        except OSError as e:
            print(f"[meta] 写入失败: {d.filename} — {e}")

    print(
        f"回填完成: 哈希回填 {hashed} 份 / 跳过 {hash_skipped} 份; "
        f"meta 写入 {meta_written} 份 / 已存在 {meta_skipped} 份"
    )


async def main() -> None:
    print(
        f"注意: embeddings_meta.json 回填假设存量向量由当前配置嵌入: "
        f"model={PROJECT_CONFIG.EMBEDDING_MODEL}, dim={PROJECT_CONFIG.EMBEDDING_DIM}"
    )
    await Tortoise.init(config=_tortoise_config())
    try:
        await backfill()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        LOGGER.error(f"增量更新字段回填失败: {e}\n{traceback.format_exc()}")
        sys.exit(1)
