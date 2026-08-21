import asyncio

import pytest

from applications.jiayueyang.rag.chunker import chunk_document
from common.file_utils import read_upload_with_cap, sanitize_upload_filename
from configure import CELERY_CONFIG, PROJECT_CONFIG, RAG_PROMPTS
from core.exceptions import ParameterException


def test_merged_config_keeps_both_application_families():
    assert PROJECT_CONFIG.TEST_CASE_OUTPUT_DIR
    assert PROJECT_CONFIG.TICKET_MODEL_POOL
    assert PROJECT_CONFIG.IDE_DATABASE_URL.startswith("mysql+aiomysql://")
    assert PROJECT_CONFIG.RAG_OUTPUT_DIR
    assert PROJECT_CONFIG.VECTOR_BACKEND in {"milvus", "chromadb"}
    assert PROJECT_CONFIG.EMBEDDING_MODEL
    assert "naive_rag_response" in RAG_PROMPTS


def test_celery_schedule_keeps_dispatch_and_rag_maintenance():
    schedule = CELERY_CONFIG.CELERY_CONFIG["beat_schedule"]
    assert {
        "scan-task-center-tasks",
        "rag-sweep-stale-documents",
        "rag-gc-orphan-chunks",
    }.issubset(schedule)


def test_recursive_chunker_preserves_order_and_overlap():
    text = "第一段内容。" * 120
    chunks = chunk_document(text, chunk_token_size=40, chunk_overlap_token_size=8)

    assert len(chunks) > 1
    assert [chunk["chunk_order_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk["content"].strip() for chunk in chunks)


def test_upload_filename_sanitization_blocks_invalid_names():
    assert sanitize_upload_filename("../../report.pdf") == "report.pdf"
    assert sanitize_upload_filename(r"C:\\temp\\report.pdf") == "report.pdf"
    with pytest.raises(ParameterException):
        sanitize_upload_filename("..")
    with pytest.raises(ParameterException):
        sanitize_upload_filename("bad\x00name.pdf")


def test_upload_reader_enforces_actual_size_cap():
    class Upload:
        def __init__(self):
            self.parts = iter((b"1234", b"5678", b""))

        async def read(self, _size):
            return next(self.parts)

    with pytest.raises(ParameterException):
        asyncio.run(read_upload_with_cap(Upload(), max_bytes=7))
