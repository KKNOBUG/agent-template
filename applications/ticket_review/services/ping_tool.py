from __future__ import annotations

import asyncio
import inspect
import ipaddress
import json
import logging
import platform
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)

PING_MCP_SERVER_KEY = "ping_tool"
PING_TOOL_NAME = "check_ip_reachable"
PING_ALLOWED_TOOL = f"mcp__{PING_MCP_SERVER_KEY}__{PING_TOOL_NAME}"

_WINDOWS = "Windows"
_LINUX = "Linux"
_PING_TIMEOUT_SECONDS = 5
_PING_WINDOWS_ARGS = ["-n", "1", "-w", "3000"]
_PING_LINUX_ARGS = ["-c", "1", "-W", "3"]


@tool(
    PING_TOOL_NAME,
    "使用系统 ping 命令检测目标 IP 的 ICMP 连通性，只接受合法 IPv4/IPv6 地址。"
    "Windows 调用 ping -n 1 -w 3000，Linux 调用 ping -c 1 -W 3。"
    "返回 reachable=true/false 及 reason。",
    {"ip": str},
)
async def check_ip_reachable(args: dict[str, Any]) -> dict[str, Any]:
    """MCP 工具入口：接收模型传入的参数字典并返回 MCP 文本内容。"""
    raw_ip = str(args.get("ip") or "").strip()
    current_platform = platform.system()

    # 1. IP 格式校验
    try:
        ipaddress.ip_address(raw_ip)
    except ValueError:
        return _build_mcp_response(
            {
                "ip": raw_ip,
                "reachable": False,
                "reason": f"IP 地址格式非法: {raw_ip}",
                "platform": current_platform,
            }
        )

    # 2. 组装 ping 命令（无 shell 注入风险，IP 已校验）
    ping_args = ["ping"]
    if current_platform == _WINDOWS:
        ping_args.extend(_PING_WINDOWS_ARGS)
    else:
        ping_args.extend(_PING_LINUX_ARGS)
    ping_args.append(raw_ip)

    proc, reachable, reason = await _run_ping(ping_args, current_platform)

    return _build_mcp_response(
        {
            "ip": raw_ip,
            "reachable": reachable,
            "reason": reason,
            "platform": current_platform,
        }
    )


async def _run_ping(
    ping_args: list[str],
    current_platform: str,
) -> tuple[asyncio.subprocess.Process | None, bool, str]:
    """执行 ping 命令，带 5 秒超时，超时后 kill 并回收进程。"""
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *ping_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        returncode = await asyncio.wait_for(
            proc.wait(), timeout=_PING_TIMEOUT_SECONDS
        )
        if returncode == 0:
            return proc, True, "目标IP可以ping通"
        return proc, False, "目标IP未响应，或网络、防火墙禁止ICMP"
    except asyncio.TimeoutError:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=2)
            except Exception:
                pass
        return proc, False, "ping 命令执行超时（5秒），目标IP未响应"
    except FileNotFoundError:
        # 系统中不存在 ping 命令
        return proc, False, "当前运行环境未安装ping命令"
    except OSError as exc:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass
        return proc, False, f"ping 执行失败: {exc}"


def _build_mcp_response(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False),
            }
        ]
    }


async def close_stale_process() -> None:
    """兜底：若进程残留则尝试回收。"""
    pass


def create_ping_mcp_server() -> Any:
    """创建供 ClaudeAgentOptions.mcp_servers 注册的进程内 MCP server。"""
    server_kwargs: dict[str, Any] = {
        "name": PING_MCP_SERVER_KEY,
        "tools": [check_ip_reachable],
    }
    if "version" in inspect.signature(create_sdk_mcp_server).parameters:
        server_kwargs["version"] = "1.0.0"
    return create_sdk_mcp_server(**server_kwargs)