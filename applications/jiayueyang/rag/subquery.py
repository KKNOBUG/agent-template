# -*- coding: utf-8 -*-
"""子查询分解 — 复合问题拆分为多个单面查询分别召回。

复合问题（"对比 A 文档的 X 和 B 文档的 Y"、"X 的流程和 Y 的字段分别
是什么"）被 embed 成一个均值向量时, 每一面都召回不深。分解后每个子查询
独立走召回通道, 所有排名列表合并进同一个 RRF 候选池——并集语义保证
每一面的文档都有机会进池, 是否进窗口仍由重排唯一闸门决定。

成本控制:
- 单一面问题（高频路径）LLM 判定后原样通过, 不产生子查询;
- 分解结果按查询哈希缓存（1 小时 TTL）, 重复提问零 LLM 开销;
- 判定/解析失败一律回退为不分解——分解是增强, 不得阻塞或劣化主检索。
"""
import asyncio
import hashlib
import json
import time as _time
from typing import Any, Dict, List, Optional

from configure import LOGGER, PROJECT_CONFIG

from applications.jiayueyang.rag.llm import chat_completion

_DECOMPOSE_SYSTEM_PROMPT = """你是检索查询分析助手。判断用户问题是否为"复合问题"——即同时涉及多个相互独立的信息面（例如：对比两份资料的不同规定、同时询问多个互不从属的主题、要求分别说明 X 和 Y）。

判定与输出要求：
1. 若问题只围绕单一主题/单一信息面（包括同一主题下的追问、列举同一类条目），输出 is_compound=false，sub_queries 为空数组；
2. 若为复合问题，输出 is_compound=true，并拆成 2~4 个子查询。每个子查询必须：
   - 自包含：不依赖原问题的上下文即可独立检索；
   - 单一面：只覆盖原问题的一个信息面；
   - 保留原问题中的专有名词、术语、编号，不改写不翻译；
3. 严格输出 JSON：{"is_compound": true/false, "sub_queries": ["...", "..."]}，不要输出任何其他内容。"""

# 分解缓存: {查询哈希: 子查询列表}, 与 query_rewriter 同模式（TTL + 容量上限）
_CACHE: Dict[str, List[str]] = {}
_CACHE_TIMES: Dict[str, float] = {}
_CACHE_TTL = 3600.0
_CACHE_MAX = 512

# 分解 LLM 调用超时: 查询路径不可长时间挂起; 超时按"不分解"降级
_DECOMPOSE_TIMEOUT_S = 15.0


def _cache_key(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()[:16]


def _cache_get(query: str) -> Optional[List[str]]:
    key = _cache_key(query)
    if key in _CACHE and _time.time() - _CACHE_TIMES.get(key, 0) < _CACHE_TTL:
        return _CACHE[key]
    return None


def _cache_set(query: str, sub_queries: List[str]) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE_TIMES, key=_CACHE_TIMES.get)
        _CACHE.pop(oldest, None)
        _CACHE_TIMES.pop(oldest, None)
    key = _cache_key(query)
    _CACHE[key] = sub_queries
    _CACHE_TIMES[key] = _time.time()


def clear_decompose_cache() -> None:
    """清空分解缓存（术语索引/文档变化时可调用）。"""
    _CACHE.clear()
    _CACHE_TIMES.clear()


def _parse_decompose_result(raw: str, max_count: int) -> List[str]:
    """解析 LLM 分解结果; 单一面或非法输出返回空列表。"""
    text = (raw or "").strip()
    # 容忍模型偶发输出 ```json 包裹
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        # 退而提取首个 {...} 片段
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start:end + 1])
        except Exception:
            return []

    if not isinstance(data, dict) or not data.get("is_compound"):
        return []
    subs = data.get("sub_queries") or []
    result: List[str] = []
    for s in subs:
        if not isinstance(s, str):
            continue
        s = s.strip()
        if s and s not in result:
            result.append(s)
        if len(result) >= max_count:
            break
    return result


async def decompose_query(query: str) -> List[str]:
    """分解复合查询; 单一面问题 / 失败 / 超时一律返回空列表（= 不分解）。

    返回的子查询**不含原查询**——调用方负责把原查询与子查询合并为
    检索查询集合（原查询保留是对分解质量的兜底）。
    """
    q = (query or "").strip()
    if not q:
        return []
    if not PROJECT_CONFIG.SUBQUERY_DECOMPOSE_ENABLED:
        return []

    cached = _cache_get(q)
    if cached is not None:
        LOGGER.debug(f"子查询分解缓存命中: {q[:50]} → {len(cached)} 个子查询")
        return cached

    try:
        raw = await asyncio.wait_for(
            chat_completion(
                messages=q,
                system_prompt=_DECOMPOSE_SYSTEM_PROMPT,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=500,
            ),
            timeout=_DECOMPOSE_TIMEOUT_S,
        )
        subs = _parse_decompose_result(raw if isinstance(raw, str) else "", PROJECT_CONFIG.SUBQUERY_MAX_COUNT)
    except asyncio.TimeoutError:
        LOGGER.warning(f"子查询分解超时 ({_DECOMPOSE_TIMEOUT_S}s), 不分解: {q[:50]}")
        subs = []
    except Exception as exc:
        LOGGER.warning(f"子查询分解失败, 不分解: {q[:50]}, {exc}")
        subs = []

    # 单一面结论同样入缓存: 高频的单面问题不重复花 LLM 调用
    _cache_set(q, subs)
    if subs:
        LOGGER.info(f"子查询分解: {q[:50]} → {subs}")
    return subs
