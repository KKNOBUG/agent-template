from __future__ import annotations

import inspect
import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from applications.ticket_review.services.db1_pool import get_db1_cursor


DEPARTMENT_MCP_SERVER_KEY = "department_directory"
DEPARTMENT_TOOL_NAME = "resolve_center_by_org_name"
DEPARTMENT_ALLOWED_TOOL = f"mcp__{DEPARTMENT_MCP_SERVER_KEY}__{DEPARTMENT_TOOL_NAME}"
MAX_PARENT_HOPS = 3


@tool(
    DEPARTMENT_TOOL_NAME,
    "根据组织名称（如用户部门名称）在 DB1 department 表中模糊匹配部门名称，"
    "并沿 parent_id 链路向上追溯，判断所属中心是上海、苏州或无法判断。"
    "仅查询，不修改任何数据。",
    {"org_name": str},
)
async def resolve_center_by_org_name(args: dict[str, Any]) -> dict[str, Any]:
    """MCP 工具入口：接收模型传入的参数字典并返回 MCP 文本内容。"""
    org_name = str(args.get("org_name") or "")
    try:
        result = await _resolve_center_by_org_name_impl(org_name)
    except Exception as exc:
        result = _result(
            org_name.strip(),
            "无法判断",
            match_type="error",
            reason=f"DB1查询失败: {exc}",
        )

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False),
            }
        ]
    }


async def _resolve_center_by_org_name_impl(org_name: str) -> dict[str, Any]:
    """只读查询 department 表，并沿 parent_id 向上查找上海或苏州中心。"""
    raw = str(org_name or "").strip()
    if not raw:
        return _result(raw, "无法判断", match_type="none", reason="组织名称为空")

    # 原始组织名称已经明确包含中心时，无需访问数据库。
    direct_center = _center_from_name(raw)
    if direct_center:
        return _result(
            raw,
            direct_center,
            matched_department=raw,
            match_type="direct",
            path=[raw],
            reason=f"组织名称直接包含{direct_center}",
        )

    async with get_db1_cursor() as cursor:
        # 同时兼容两种情况：
        # 1. 表中名称包含 Excel 原始组织名；
        # 2. Excel 原始组织名较长，其中包含表里的部门名称。
        await cursor.execute(
            "SELECT department_id, parent_id, department_name "
            "FROM department "
            "WHERE department_name LIKE %s "
            "OR %s LIKE CONCAT('%%', department_name, '%%') "
            "ORDER BY CASE WHEN department_name = %s THEN 0 ELSE 1 END, "
            "CHAR_LENGTH(department_name) DESC",
            (f"%{raw}%", raw, raw),
        )
        rows = await cursor.fetchall()

        if not rows:
            return _result(
                raw,
                "无法判断",
                match_type="none",
                reason="department表中未找到匹配组织",
            )

        longest_path: list[str] = []
        longest_path_match = ""

        # 按数据库返回顺序检查所有候选部门；匹配到上海或苏州即返回。
        for row in rows:
            matched_name = str(row.get("department_name") or "")
            path = [matched_name] if matched_name else []

            center = _center_from_name(matched_name)
            if center:
                return _result(
                    raw,
                    center,
                    matched_department=matched_name,
                    match_type="fuzzy",
                    path=path,
                    reason=f"匹配部门名称包含{center}",
                )

            department_id = row.get("department_id")
            current_parent = row.get("parent_id")
            visited = {department_id}

            # 当前行 parent_id -> 父行 department_id，最多连续向上查三级。
            for _ in range(MAX_PARENT_HOPS):
                if current_parent in (None, "", 0, "0") or current_parent in visited:
                    break

                visited.add(current_parent)
                await cursor.execute(
                    "SELECT department_id, parent_id, department_name "
                    "FROM department "
                    "WHERE department_id = %s "
                    "LIMIT 1",
                    (current_parent,),
                )
                parent = await cursor.fetchone()
                if not parent:
                    break

                parent_name = str(parent.get("department_name") or "")
                if parent_name:
                    path.append(parent_name)

                center = _center_from_name(parent_name)
                if center:
                    return _result(
                        raw,
                        center,
                        matched_department=matched_name,
                        match_type="fuzzy",
                        path=path,
                        reason=f"匹配部门的上级链包含{center}",
                    )

                current_parent = parent.get("parent_id")

            if len(path) > len(longest_path):
                longest_path = path
                longest_path_match = matched_name

    return _result(
        raw,
        "无法判断",
        matched_department=longest_path_match,
        match_type="fuzzy",
        path=longest_path,
        reason="已找到匹配部门，但其上级链中没有上海或苏州",
    )


def _center_from_name(name: str) -> str:
    """从部门名称中识别中心；未识别时返回空字符串。"""
    if "上海" in name:
        return "上海"
    if "苏州" in name:
        return "苏州"
    return ""


def _result(
    org_name: str,
    center: str,
    *,
    matched_department: str = "",
    match_type: str = "direct",
    path: list[str] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """生成稳定的工具结果，供大模型读取 center 字段。"""
    return {
        "org_name": org_name,
        "center": center,
        "matched_department": matched_department,
        "match_type": match_type,
        "department_path": path or [],
        "reason": reason,
    }


def create_department_mcp_server() -> Any:
    """创建供 ClaudeAgentOptions.mcp_servers 注册的进程内 MCP server。"""
    server_kwargs: dict[str, Any] = {
        "name": DEPARTMENT_MCP_SERVER_KEY,
        "tools": [resolve_center_by_org_name],
    }
    if "version" in inspect.signature(create_sdk_mcp_server).parameters:
        server_kwargs["version"] = "1.0.0"
    return create_sdk_mcp_server(**server_kwargs)
