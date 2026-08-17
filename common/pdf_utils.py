# -*- coding: utf-8 -*-
"""PDF 工具——大文档的页数统计与分片。"""

import io
from pathlib import Path
from typing import List, Tuple

from pypdf import PdfReader, PdfWriter

from configure import PROJECT_CONFIG


def get_pdf_page_count(file_bytes: bytes) -> int:
    """返回 PDF 的页数。"""
    reader = PdfReader(io.BytesIO(file_bytes))
    return len(reader.pages)


def split_pdf(
    file_bytes: bytes,
    original_filename: str,
    max_pages: int = PROJECT_CONFIG.PDF_SPLIT_MAX_PAGES,
) -> List[Tuple[str, bytes]]:
    """将 PDF 切分为多个分片，每个分片不超过 *max_pages* 页。

    :return: ``(分片文件名, 分片字节流)`` 元组列表。
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)

    if total_pages <= max_pages:
        return [(original_filename, file_bytes)]

    stem = Path(original_filename).stem
    suffix = Path(original_filename).suffix
    parts: List[Tuple[str, bytes]] = []

    start = 0
    part_num = 1
    while start < total_pages:
        end = min(start + max_pages, total_pages)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        part_bytes = buf.read()

        part_filename = f"{stem}_part{part_num:03d}{suffix}"
        parts.append((part_filename, part_bytes))
        start = end
        part_num += 1

    return parts
