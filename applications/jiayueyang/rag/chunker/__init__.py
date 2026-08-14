# -*- coding: utf-8 -*-
"""文档分块模块 — 仅递归字符切分（R 策略），实现移植自 LightRAG"""

from typing import Any, Dict, List

from applications.jiayueyang.rag.chunker.recursive_character import chunking_by_recursive_character
from configure import PROJECT_CONFIG


def chunk_document(
        text: str,
        chunk_token_size: int = PROJECT_CONFIG.CHUNK_SIZE,
        chunk_overlap_token_size: int = PROJECT_CONFIG.CHUNK_OVERLAP_SIZE,
        **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    对文档执行递归字符分块

    :param text: 文档正文（Markdown 或纯文本）
    :param chunk_token_size: 目标分块 token 大小
    :param chunk_overlap_token_size: 相邻分块的重叠 token 大小
    :param kwargs: 透传给策略函数
    :return: {content, tokens, chunk_order_index} 字典列表
    """
    if not text or not text.strip():
        return []

    return chunking_by_recursive_character(
        text,
        chunk_token_size=chunk_token_size,
        chunk_overlap_token_size=chunk_overlap_token_size,
        **kwargs,
    )


__all__ = [
    "chunk_document",
    "chunking_by_recursive_character",
]
