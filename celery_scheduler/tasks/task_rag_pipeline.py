# -*- coding: utf-8 -*-
"""RAG 文档处理 Celery 任务（替代原 asyncio 后台任务）。

任务仅接收 job_id, 其余参数均从文档状态存储（MySQL keenrobot_rag_document 表）读取,
与 zsj 的 task_test_case_gen 等即发式任务范式一致。
"""
import traceback
from typing import Any, Dict

from celery_scheduler.celery_worker import celery
from configure import LOGGER


@celery.task(
    name="celery_scheduler.tasks.task_rag_pipeline.process_document_task",
    soft_time_limit=3300,
    time_limit=3600,
)
async def process_document_task(job_id: str) -> Dict[str, Any]:
    """Celery 入口: 按 job_id 后台执行文档处理流水线（解析 → 术语 → 多模态 → 分块 → 嵌入）。

    消息仅携带 job_id; 源文件字节流由 Worker 从提交时落盘的留档目录
    （input/<job_id>/）重新读取。

    :param job_id: 文档任务ID
    """
    try:
        from applications.jiayueyang.services.rag_pipeline import RagPipelineService
        from applications.jiayueyang.services.rag_service import RagDocumentService

        pipeline_service = RagPipelineService(document_service=RagDocumentService())
        # execution_token 传 Celery task id: 分布式锁以此判定重入
        # （acks_late 重投递任务 task_id 不变, 可接管续跑; 不同 token 的并行执行被拒）
        return await pipeline_service.process_document(
            job_id=job_id,
            execution_token=process_document_task.request.id,
        )
    except Exception as exc:
        LOGGER.error(
            f"RAG 文档处理任务异常: \n"
            f"job_id: {job_id}\n"
            f"错误类型: {type(exc).__name__}\n"
            f"错误描述: {exc}\n"
            f"错误回溯: {traceback.format_exc()}\n"
        )
        return {"success": False, "error": str(exc)}


@celery.task(
    name="celery_scheduler.tasks.task_rag_pipeline.rollback_document_task",
    soft_time_limit=1500,
    time_limit=1800,
)
async def rollback_document_task(job_id: str) -> Dict[str, Any]:
    """Celery 入口: 增量更新失败后, 把文档回滚到上一版本。

    执行体（RagPipelineService.execute_rollback）: 先用 prev 归档的
    embeddings.json 重写向量库, 再恢复产物/留档目录与文档字段。
    短任务（秒级~分钟级）, 时限远小于完整处理任务。

    :param job_id: 文档任务ID
    """
    try:
        from applications.jiayueyang.services.rag_pipeline import RagPipelineService
        from applications.jiayueyang.services.rag_service import RagDocumentService

        pipeline_service = RagPipelineService(document_service=RagDocumentService())
        return await pipeline_service.execute_rollback(
            job_id=job_id,
            execution_token=rollback_document_task.request.id,
        )
    except Exception as exc:
        LOGGER.error(
            f"RAG 文档回滚任务异常: \n"
            f"job_id: {job_id}\n"
            f"错误类型: {type(exc).__name__}\n"
            f"错误描述: {exc}\n"
            f"错误回溯: {traceback.format_exc()}\n"
        )
        return {"success": False, "error": str(exc)}
