# -*- coding: utf-8 -*-
"""docling 内存探针: 逐页转换 PDF, 打印每页结束后的进程提交内存,
用于定位解析过程中内存无限增长的来源阶段。

用法（项目根目录, venv 内）:
    python services/scripts/mem_probe.py 路径/文件.pdf
    python services/scripts/mem_probe.py 文件.pdf --pages 5        # 只探前 5 页
    python services/scripts/mem_probe.py 文件.pdf --no-table       # 关表格结构识别
    python services/scripts/mem_probe.py 文件.pdf --no-picture     # 关图片分类/描述
    python services/scripts/mem_probe.py 文件.pdf --no-ocr         # 关 OCR

判读: commit_GB 若随页数单调上涨不回落, 即存在增长源;
配合 --no-* 开关二分（每次只关一个功能重跑）, 锁定具体功能。
"""
import argparse
import ctypes
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class _PMCE(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _mem_counters() -> _PMCE:
    pmc = _PMCE()
    pmc.cb = ctypes.sizeof(_PMCE)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
    return pmc


def commit_gb() -> float:
    """进程私有提交内存（GB）—— 内核 OOM 判定用的就是这个量。"""
    return _mem_counters().PagefileUsage / (1024 ** 3)


def rss_gb() -> float:
    """进程物理内存工作集（GB）。"""
    return _mem_counters().WorkingSetSize / (1024 ** 3)


def main() -> None:
    parser = argparse.ArgumentParser(description="docling 内存探针")
    parser.add_argument("pdf", help="待探测的 PDF 文件路径")
    parser.add_argument("--pages", type=int, default=0, help="只探测前 N 页（0 = 全部）")
    parser.add_argument("--no-table", action="store_true", help="关闭表格结构识别")
    parser.add_argument("--no-picture", action="store_true", help="关闭图片分类/描述")
    parser.add_argument("--no-ocr", action="store_true", help="关闭 OCR")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    data = pdf_path.read_bytes()

    from common.pdf_utils import get_pdf_page_count

    total = get_pdf_page_count(data)
    num_pages = total if args.pages <= 0 else min(args.pages, total)
    print(f"PDF: {pdf_path.name} (共 {total} 页, 探测前 {num_pages} 页)")
    print(
        f"开关: table={not args.no_table} "
        f"picture={not args.no_picture} ocr={not args.no_ocr}"
    )

    import gc

    import common.docling_native as dn
    from docling.datamodel.base_models import DocumentStream, InputFormat

    def _make_converter():
        conv = dn._create_converter(
            do_ocr=not args.no_ocr, force_ocr=False
        )
        if args.no_table or args.no_picture:
            opts = conv.format_to_options[InputFormat.PDF].pipeline_options
            if args.no_table:
                opts.do_table_structure = False
            if args.no_picture:
                opts.do_picture_classification = False
                opts.do_picture_description = False
        return conv

    print(f"\n{'page':>4}  {'sec':>6}  {'commit_GB':>9}  {'rss_GB':>7}  {'pics':>4}  delta")
    print(f"{'init':>4}  {'-':>6}  {commit_gb():9.2f}  {rss_gb():7.2f}  {'-':>4}  -")

    # 与 worker 新策略一致: 每页新建 converter、用后释放（每页约 5 秒模型重载）
    prev = commit_gb()
    for i in range(1, num_pages + 1):
        t0 = time.time()
        converter = _make_converter()
        source = DocumentStream(name=pdf_path.name, stream=io.BytesIO(data))
        try:
            result = converter.convert(source, raises_on_error=False, page_range=[i, i])
            pics = len(result.document.pictures) if result.document else 0
        finally:
            del converter, source
            gc.collect()
        now = commit_gb()
        delta = now - prev
        flag = "  <-- 持续增长" if delta > 0.5 else ""
        print(
            f"{i:>4}  {time.time() - t0:6.1f}  {now:9.2f}  "
            f"{rss_gb():7.2f}  {pics:>4}  {delta:+.2f}GB{flag}"
        )
        prev = now

    print("\n完成。健康状态: commit_GB 应随页数基本平稳（释放生效）;")
    print("若仍单调上涨 → 增长源在释放不掉的层, 用 --no-table / --no-picture / --no-ocr 二分。")


if __name__ == "__main__":
    main()
