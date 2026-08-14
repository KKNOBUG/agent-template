# -*- coding: utf-8 -*-
"""导出用户对话历史（用于后续分析 / 改善）。

对话持久化于 MySQL（keenrobot_rag_conversation / _message 表）,
本脚本经 Tortoise ORM 读取并导出, 不依赖 Web 应用启动。

用法（项目根目录）:
    python services/scripts/export_conversations.py
    python services/scripts/export_conversations.py --csv            # 同时导出扁平化 CSV
    python services/scripts/export_conversations.py --out <path>

产出:
    - JSON: 按会话聚合, 每个会话含 messages 列表（role/content/time）;
    - CSV : 扁平化为「每行一条消息」, 便于 Excel / pandas 分析（utf-8-sig, 中文不乱码）。
"""
import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tortoise import Tortoise  # noqa: E402

from configure import PROJECT_CONFIG  # noqa: E402

DEFAULT_OUT = PROJECT_ROOT / "output" / "conversations_export.json"
_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _fmt(value: Optional[datetime]) -> str:
    return value.strftime(_TIME_FMT) if value else ""


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


async def collect() -> List[Dict[str, Any]]:
    from applications.jiayueyang.models.conversation_model import (
        RagConversation,
        RagConversationMessage,
    )

    convs = await RagConversation.all().order_by("-pinned", "-updated_time")
    result: List[Dict[str, Any]] = []
    for conv in convs:
        msgs = await RagConversationMessage.filter(
            conversation_id=conv.id,
        ).order_by("seq")
        result.append({
            "conversation_id": conv.id,
            "username": conv.username or "User",
            "title": conv.title or "",
            "pinned": bool(conv.pinned),
            "created_time": _fmt(conv.created_time),
            "updated_time": _fmt(conv.updated_time),
            "message_count": len(msgs),
            "messages": [
                {"role": m.role, "content": m.content or "", "time": _fmt(m.created_time)}
                for m in msgs
            ],
        })
    return result


def export(out: Path, want_csv: bool) -> None:
    result = asyncio.run(_run())

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    total_msgs = sum(c["message_count"] for c in result)
    print(f"已导出 {len(result)} 个会话 / {total_msgs} 条消息 → {out}")

    if want_csv:
        csv_path = out.with_suffix(".csv")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["conversation_id", "username", "title", "role", "content", "time"])
            for conv in result:
                for m in conv["messages"]:
                    writer.writerow([
                        conv["conversation_id"], conv["username"], conv["title"],
                        m["role"], m["content"], m["time"],
                    ])
        print(f"CSV → {csv_path}")


async def _run() -> List[Dict[str, Any]]:
    await Tortoise.init(config=_tortoise_config())
    try:
        return await collect()
    finally:
        await Tortoise.close_connections()


def main() -> None:
    parser = argparse.ArgumentParser(description="导出用户对话历史（MySQL → JSON/CSV）")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"JSON 输出路径（默认 {DEFAULT_OUT}）")
    parser.add_argument("--csv", action="store_true", help="同时导出扁平化 CSV")
    args = parser.parse_args()
    export(args.out, args.csv)


if __name__ == "__main__":
    main()
