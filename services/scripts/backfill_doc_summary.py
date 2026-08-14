# -*- coding: utf-8 -*-
"""一次性回填: 为存量文档生成文档摘要（文档级召回索引的数据源）。

v0.10 引入文档级召回后, 新入库文档由入库流水线（阶段 1.6）生成
``summary.json``; 存量 complete 文档没有该产物, 不会进入查询侧的
文档摘要索引。本脚本逐份补齐:

1. 产物已存在（summary.json 可读且含 summary + vector）→ 跳过生成;
   文档表 summary 字段与产物不一致时（旧版前 15 字符占位）同步回填;
2. 产物缺失 → 读取结果包目录内清洗后的 markdown（``{文件名主干}.md``,
   与流水线阶段 1.6 的输入同口径）, 生成摘要并嵌入, 落盘 summary.json,
   回写文档表 summary 字段。

用法（项目根目录）:
    python services/scripts/backfill_doc_summary.py

幂等: 已有产物跳过, 可安全重复执行（失败的文档重跑即补齐）。
前提: .env 的 DATABASE_* 已配置; LLM / 嵌入服务可达。
注: 每份文档 1 次 LLM + 1 次嵌入调用, 文档较多时建议低峰期执行。
"""
import asyncio
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

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


def _load_summary_file(summary_file: Path) -> Optional[Dict[str, Any]]:
    """读取已有摘要产物; 缺失/不可读/不完整返回 None。"""
    if not summary_file.is_file():
        return None
    try:
        data = json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception as e:
        LOGGER.warning(f"摘要产物不可读, 将重新生成: {summary_file}, {e}")
        return None
    if not data.get("summary") or not data.get("vector"):
        return None
    return data


async def backfill() -> None:
    from applications.jiayueyang.models.rag_document_model import RagDocument

    docs = await RagDocument.filter(status="complete")
    if not docs:
        print("没有解析完成的文档, 无需回填。")
        return

    # 延迟导入: 需要向量库/LLM 客户端就绪, 且只有真正要生成时才需要
    from applications.jiayueyang.rag.doc_summary import generate_doc_summary

    generated = skipped = synced = failed = 0
    for d in docs:
        bundle_dir = Path(d.output_path or "")
        if not bundle_dir.is_dir():
            failed += 1
            print(f"[摘要] 跳过（结果包目录不存在）: {d.filename} ({d.output_path})")
            continue

        summary_file = bundle_dir / "summary.json"
        existing = _load_summary_file(summary_file)

        if existing is not None:
            skipped += 1
            # 文档表 summary 仍是旧版占位 → 用产物同步（字段级更新）
            if (d.summary or "") != existing["summary"]:
                await RagDocument.filter(job_id=d.job_id).update(
                    summary=existing["summary"]
                )
                synced += 1
                print(f"[摘要] 产物已存在, 同步文档表: {d.filename}")
            else:
                print(f"[摘要] 产物已存在, 跳过: {d.filename}")
            continue

        md_path = bundle_dir / f"{Path(d.filename).stem}.md"
        if not md_path.is_file():
            failed += 1
            print(f"[摘要] 跳过（清洗后的 markdown 不存在）: {d.filename} ({md_path})")
            continue

        try:
            markdown = md_path.read_text(encoding="utf-8")
            summary_data = await generate_doc_summary(markdown, d.filename)
            summary_file.write_text(
                json.dumps(
                    {**summary_data, "created_at": int(time.time())},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            await RagDocument.filter(job_id=d.job_id).update(
                summary=summary_data["summary"]
            )
            generated += 1
            print(f"[摘要] 已生成: {d.filename} ({len(summary_data['summary'])} 字)")
        except Exception as e:
            failed += 1
            LOGGER.warning(f"摘要回填失败: {d.filename}, {e}")
            print(f"[摘要] 失败: {d.filename} — {type(e).__name__}: {e}")

    print(
        f"回填完成: 生成 {generated} 份, 已存在 {skipped} 份"
        f"（其中同步文档表 {synced} 份）, 失败 {failed} 份"
    )


async def main() -> None:
    await Tortoise.init(config=_tortoise_config())
    try:
        await backfill()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        LOGGER.error(f"文档摘要回填失败: {e}\n{traceback.format_exc()}")
        sys.exit(1)
