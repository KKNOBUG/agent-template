# -*- coding: utf-8 -*-
"""Sidecar 文件写入器——将 DoclingDocument JSON 转换为 LightRAG 兼容文件。

产出：
  - blocks.jsonl   —— 阅读流文本块（每行一个 JSON）
  - drawings.json  —— 图片元数据
  - tables.json    —— 表格数据（以稳定 id 为键）
  - meta.json      —— 解析元数据（引擎、时间戳、哈希）
"""

import hashlib
import json
import re
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from applications.jiayueyang.rag.table_rows import is_toc_table


def merge_docling_documents(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """将多个 DoclingDocument 字典合并为一个组合文档。

    调整 ``body.children`` 中的 ``$ref`` 指针，使其能正确索引到
    拼接后的 ``texts``、``tables`` 与 ``pictures`` 数组。

    用于大 PDF 被拆分为子文档的场景——每个子文档各自产出一份
    docling JSON，而整篇文档需要一份统一的 sidecar。
    """
    if not documents:
        return {}
    if len(documents) == 1:
        return dict(documents[0])

    # 从第一个文档的副本开始，然后清空其子节点
    merged: Dict[str, Any] = dict(documents[0])
    first_body = documents[0].get("body", {}) if isinstance(documents[0].get("body"), dict) else {}
    merged["body"] = {k: v for k, v in first_body.items() if k != "children"}
    merged["body"]["children"] = []
    merged["texts"] = list(documents[0].get("texts") or [])
    merged["tables"] = list(documents[0].get("tables") or [])
    merged["pictures"] = list(documents[0].get("pictures") or [])

    # 处理其余文档
    text_offset = len(merged["texts"])
    table_offset = len(merged["tables"])
    picture_offset = len(merged["pictures"])

    for doc in documents[1:]:
        body = doc.get("body", {}) if isinstance(doc.get("body"), dict) else {}
        children = list(body.get("children", []))

        n_texts = len(doc.get("texts") or [])
        n_tables = len(doc.get("tables") or [])
        n_pictures = len(doc.get("pictures") or [])

        # 调整 children 中的 $ref 下标
        for child in children:
            if not isinstance(child, dict):
                merged["body"]["children"].append(child)
                continue
            ref = child.get("$ref", "")
            kind, idx = _parse_ref(ref)
            new_child = dict(child)
            if kind == "texts" and isinstance(idx, int):
                new_child["$ref"] = f"#/texts/{idx + text_offset}"
            elif kind == "tables" and isinstance(idx, int):
                new_child["$ref"] = f"#/tables/{idx + table_offset}"
            elif kind == "pictures" and isinstance(idx, int):
                new_child["$ref"] = f"#/pictures/{idx + picture_offset}"
            merged["body"]["children"].append(new_child)

        merged["texts"].extend(doc.get("texts") or [])
        merged["tables"].extend(doc.get("tables") or [])
        merged["pictures"].extend(doc.get("pictures") or [])

        text_offset += n_texts
        table_offset += n_tables
        picture_offset += n_pictures

    return merged


def write_sidecar(
    docling_json_path: str,
    output_dir: str,
    *,
    engine: str = "docling",
    md_path: Optional[str] = None,
) -> Dict[str, str]:
    """将 DoclingDocument JSON 转换为 LightRAG sidecar 文件。

    :param docling_json_path: docling 产出的 ``<stem>.json`` 路径。
    :param output_dir: sidecar 文件的写入目录（如 ``output/<stem>/``）。
    :param engine: 解析引擎名称，写入 ``meta.json``。
    :param md_path: 可选的配套 ``<stem>.md`` 路径，用于阅读顺序兜底。
    :return: 文件类型到绝对路径的映射字典。
    """
    with open(docling_json_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. meta.json
    meta = _build_meta(doc, engine)
    meta_path = out / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_hash = _doc_hash_prefix(doc)

    # 2. blocks.jsonl —— 阅读流文本块（按 LightRAG 约定，meta 行在前）
    blocks = _build_blocks(doc, md_path, doc_hash)
    blocks_path = out / "blocks.jsonl"
    with open(blocks_path, "w", encoding="utf-8") as f:
        # meta 行（LightRAG 约定）
        meta_line = {
            "type": "meta", "format": "lightrag", "version": "1.0",
            "document_name": Path(docling_json_path).stem,
            "document_hash": doc_hash, "parse_engine": engine,
            "parse_time": int(_time.time()),
            "blocks": len(blocks),
            "table_file": bool(tables_raw := _build_tables(doc, doc_hash)),
            "drawing_file": bool(_build_drawings_raw(doc)),
            "equation_file": False,
            "asset_dir": bool(Path(output_dir, "artifacts").is_dir()),
        }
        f.write(json.dumps(meta_line, ensure_ascii=False) + "\n")
        for block in blocks:
            f.write(json.dumps(block, ensure_ascii=False) + "\n")

    # 3. drawings.json —— 图片（dict 格式，LightRAG 约定）
    drawings = _build_drawings(doc, doc_hash)
    drawings_path = out / "drawings.json"
    drawings_content = {"version": "1.0", "drawings": drawings}
    drawings_path.write_text(json.dumps(drawings_content, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. tables.json —— 表格（带 version 的 dict 格式）
    tables_raw = _build_tables(doc, doc_hash)
    tables_path = out / "tables.json"
    tables_content = {"version": "1.0", "tables": tables_raw}
    tables_path.write_text(json.dumps(tables_content, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "meta": str(meta_path.resolve()),
        "blocks": str(blocks_path.resolve()),
        "drawings": str(drawings_path.resolve()),
        "tables": str(tables_path.resolve()),
    }


# ---------------------------------------------------------------------------
# 构建器
# ---------------------------------------------------------------------------

def _build_meta(doc: Dict[str, Any], engine: str) -> Dict[str, Any]:
    return {
        "parse_engine": engine,
        "parse_time": int(_time.time()),
        "document_hash": _doc_hash(doc),
        "schema_name": doc.get("schema_name", ""),
        "origin": doc.get("origin", {}),
    }


def _build_blocks(doc: Dict[str, Any], md_path: Optional[str], doc_hash: str) -> List[Dict[str, Any]]:
    """依据 body.children 或 Markdown 标题构建阅读流块。"""
    blocks: List[Dict[str, Any]] = []
    body = doc.get("body", {})
    children = body.get("children", []) if isinstance(body, dict) else []

    texts = doc.get("texts") or []
    tables = doc.get("tables") or []
    pictures = doc.get("pictures") or []

    block_idx = 0
    current_heading = ""
    current_level = 0
    parent_headings: List[str] = []

    def _make_block(content: str, heading: str, level: int, is_title: bool = False) -> Dict[str, Any]:
        bid = _block_id(doc_hash, block_idx, heading, content)
        return {
            "type": "content", "format": "plain_text",
            "blockid": bid,
            "content": content, "heading": heading,
            "level": level, "parent_headings": list(parent_headings),
            "session_type": "body", "table_slice": "none",
            "positions": [],
            "is_title_block": is_title,
        }

    for child_ref in children:
        ref = child_ref.get("$ref", "") if isinstance(child_ref, dict) else str(child_ref)
        kind, idx = _parse_ref(ref)

        if not isinstance(idx, int) or idx < 0:
            continue
        if kind == "texts" and idx < len(texts):
            item = texts[idx]
            label = item.get("label", "")
            text = item.get("text", "")
            if label in ("title", "section_header"):
                level = 1 if label == "title" else item.get("level", 1)
                current_heading = text
                current_level = level
                block_idx += 1
                blocks.append(_make_block("", current_heading, current_level, label == "title"))
            else:
                block_idx += 1
                blocks.append(_make_block(text, current_heading, current_level))

        elif kind == "tables" and idx < len(tables):
            block_idx += 1
            blocks.append(_make_block(
                _table_to_markdown_placeholder(tables[idx], idx),
                current_heading, current_level,
            ))

        elif kind == "pictures" and isinstance(idx, int) and idx < len(pictures):
            block_idx += 1
            blocks.append(_make_block(
                _picture_to_placeholder(pictures[idx], idx),
                current_heading, current_level,
            ))

    if not blocks and md_path and Path(md_path).exists():
        md_text = Path(md_path).read_text(encoding="utf-8")
        blocks = _blocks_from_markdown(md_text, doc_hash)

    return blocks


def _build_drawings_raw(doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """检查是否存在图片（用于 meta 行）。"""
    d = {}
    for i, pic in enumerate(doc.get("pictures") or []):
        if isinstance(pic, dict):
            d[str(i)] = pic
    return d


def _build_drawings(doc: Dict[str, Any], doc_hash: str) -> Dict[str, Dict[str, Any]]:
    """构建 drawings.json 条目（以 id 为键的 dict，LightRAG 约定）。"""
    drawings: Dict[str, Dict[str, Any]] = {}
    for i, pic in enumerate(doc.get("pictures") or []):
        if not isinstance(pic, dict):
            continue
        image = pic.get("image") or {}
        uri = image.get("uri", "")
        did = f"im-{doc_hash}-{i:04d}"
        drawings[did] = {
            "id": did, "path": uri,
            "width": image.get("width") or pic.get("width"),
            "height": image.get("height") or pic.get("height"),
            "mimetype": image.get("mimetype", "image/png"),
            "captions": [c.get("text", "") for c in (pic.get("captions") or []) if isinstance(c, dict)],
            "footnotes": [], "prov": pic.get("prov", []),
        }
    return drawings


def _build_tables(doc: Dict[str, Any], doc_hash: str) -> Dict[str, Dict[str, Any]]:
    """构建 tables.json 条目（以 id 为键的 dict）。"""
    tables: Dict[str, Dict[str, Any]] = {}
    for i, tbl in enumerate(doc.get("tables") or []):
        if not isinstance(tbl, dict):
            continue
        tid = f"tb-{doc_hash}-{i:04d}"
        data = tbl.get("data") or {}
        rows = _rows_from_grid(data) if isinstance(data, dict) else []
        # 目录表不写入 tables.json（md 侧已由 clean_markdown 清洗,
        # 此处统一剔除, 使行级分块 / VLM 分析等全部消费端天然干净）
        if is_toc_table(rows):
            continue
        num_rows = int(data.get("num_rows") or len(rows) or 0) if isinstance(data, dict) else len(rows)
        num_cols = int((data.get("num_cols") if isinstance(data, dict) else 0) or (max((len(r) for r in rows), default=0)))
        tables[tid] = {
            "body": _render_table_html(data),
            "captions": [c.get("text", "") for c in (tbl.get("captions") or []) if isinstance(c, dict)],
            "header_body": _render_table_html({"grid": rows[:1]}) if rows else "<table></table>",
            "num_rows": num_rows, "num_cols": num_cols,
        }
    return tables


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _doc_hash(doc: Dict[str, Any]) -> str:
    return _doc_hash_prefix(doc)


def _doc_hash_prefix(doc: Dict[str, Any]) -> str:
    raw = json.dumps(doc.get("body", {}), sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def _block_id(doc_hash: str, block_idx: int, heading: str, content: str) -> str:
    """计算 blockid：md5(doc_hash:index:heading:content)，与 LightRAG 一致。"""
    s = f"{doc_hash}:{block_idx}:{heading}:{content}"
    return hashlib.md5(s.encode()).hexdigest()


def _parse_ref(ref: str) -> Tuple[str, Optional[int]]:
    """解析形如 '#/texts/3' 的 JSON Pointer 引用 → ('texts', 3)。"""
    if not ref.startswith("#/"):
        return (ref, None)
    parts = ref[2:].split("/")
    kind = parts[0] if parts else ""
    try:
        idx = int(parts[1]) if len(parts) > 1 else None
    except ValueError:
        idx = None
    return (kind, idx)


def _table_to_markdown_placeholder(tbl: Dict[str, Any], idx: int) -> str:
    """将 docling 表格渲染为 Markdown（与 LightRAG 的处理方式一致）。"""
    data = tbl.get("data") or {}
    rows = _rows_from_grid(data) if isinstance(data, dict) else []
    if not rows:
        return f"<table id=\"tb-{idx:04d}\"></table>"
    md_rows = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    header_sep = "|" + "|".join(["---"] * len(rows[0])) + "|"
    return "\n".join([md_rows[0], header_sep] + md_rows[1:])


def _picture_to_placeholder(pic: Dict[str, Any], idx: int) -> str:
    """将图片渲染为 drawing 占位符。"""
    image = pic.get("image") or {}
    uri = image.get("uri", "")
    return f"<drawing id=\"im-{idx:04d}\" path=\"{uri}\" />"


# ---------------------------------------------------------------------------
# 表格辅助函数——与 LightRAG 的 docling IR 构建器保持一致
# Docling 表格数据格式：{"data": {"grid": [[{"text":"..."},...],...], "num_rows":N, "num_cols":M}}
# ---------------------------------------------------------------------------

def _rows_from_grid(data: Any) -> List[List[str]]:
    """从 docling 网格中提取单元格文本（与 LightRAG 的 _rows_from_grid 一致）。"""
    out: List[List[str]] = []
    if not isinstance(data, dict):
        return out
    grid = data.get("grid")
    if not isinstance(grid, list):
        return out
    for row in grid:
        if not isinstance(row, list):
            continue
        out.append([str((c or {}).get("text", "") if isinstance(c, dict) else c) for c in row])
    return out


def _render_table_html(data: Any) -> str:
    """将 docling 表格数据渲染为 HTML <table>。"""
    grid = data.get("grid") if isinstance(data, dict) else None
    rows = _rows_from_grid(data) if isinstance(data, dict) else _rows_from_grid({})
    if not rows:
        return "<table></table>"
    rows_html = []
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{c}</{tag}>" for c in row)
        rows_html.append(f"<tr>{cells}</tr>")
    return f"<table>{''.join(rows_html)}</table>"


def _blocks_from_markdown(md_text: str, doc_hash: str) -> List[Dict[str, Any]]:
    """兜底方案：从 Markdown 标题构建文本块。"""
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    blocks: List[Dict[str, Any]] = []
    idx = 0
    current_heading = ""
    current_level = 0
    for part in heading_re.split(md_text):
        part = part.strip()
        if not part:
            continue
        m = heading_re.match(part) if part.startswith("#") else None
        if m:
            current_level, current_heading = len(m.group(1)), m.group(2)
            idx += 1
            blocks.append({
                "type": "content", "format": "plain_text", "content": "",
                "heading": current_heading, "level": current_level,
                "parent_headings": [], "session_type": "body", "table_slice": "none",
                "positions": [], "is_title_block": False,
                "blockid": _block_id(doc_hash, idx, current_heading, ""),
            })
        else:
            idx += 1
            blocks.append({
                "type": "content", "format": "plain_text", "content": part,
                "heading": current_heading, "level": current_level,
                "parent_headings": [], "session_type": "body", "table_slice": "none",
                "positions": [], "is_title_block": False,
                "blockid": _block_id(doc_hash, idx, current_heading, part),
            })
    return blocks
