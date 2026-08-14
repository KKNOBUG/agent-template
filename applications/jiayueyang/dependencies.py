# -*- coding: utf-8 -*-
"""jiayueyang RAG 模块依赖注入工厂。

提供文档状态管理服务与流水线服务的依赖注入工厂函数。

使用方式:
    from applications.jiayueyang.dependencies import get_rag_document_service, get_rag_services

    @router.get("/documents")
    async def list_documents(
            document_service: RagDocumentService = Depends(get_rag_document_service),
    ):
        return SuccessResponse(data=document_service.get_all_documents())

注意: RagDocumentService 持有全局唯一的内存文档状态, 必须以单例方式使用;
RagPipelineService 依赖该单例, 同样全局唯一。
"""
from dataclasses import dataclass

from applications.jiayueyang.services.chat_service import ConversationService
from applications.jiayueyang.services.rag_pipeline import RagPipelineService
from applications.jiayueyang.services.rag_service import RagDocumentService

# 模块级单例: Web 进程内全局唯一
_rag_document_service = RagDocumentService()
# 启动巡检（sweep_stale_documents, 异步）已移至 backend_main 的 lifespan 内、
# 数据库初始化完成之后执行: 基于心跳/Celery 任务状态判定, 仅标记确定性
# 死亡的任务为失败, 仅 Web 重启时不会误伤 Worker 仍在处理的任务
_rag_pipeline_service = RagPipelineService(document_service=_rag_document_service)
# 对话历史服务单例（无状态, 操作 ORM）
_conversation_service = ConversationService()


@dataclass
class RagServices:
    """RAG 模块服务组合。

    用于需要同时操作文档状态与处理流水线的复杂业务场景。
    """
    document: RagDocumentService
    pipeline: RagPipelineService


async def get_rag_document_service() -> RagDocumentService:
    """获取文档状态管理服务单例"""
    return _rag_document_service


async def get_rag_pipeline_service() -> RagPipelineService:
    """获取文档处理流水线服务单例"""
    return _rag_pipeline_service


async def get_rag_services() -> RagServices:
    """获取 RAG 模块组合服务"""
    return RagServices(
        document=_rag_document_service,
        pipeline=_rag_pipeline_service,
    )


async def get_conversation_service() -> ConversationService:
    """获取对话历史管理服务单例"""
    return _conversation_service
