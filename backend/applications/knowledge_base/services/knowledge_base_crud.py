# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : knowledge_base_crud.py
@DateTime: 2026/6/9
"""
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import UploadFile
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from tortoise.expressions import Q

from backend.applications.base.rag.chroma_store import chroma_store
from backend.applications.base.rag.embeddings import get_embedding
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.knowledge_base.models.knowledge_base_model import (
    Document,
    DocumentChunk,
    KnowledgeBase,
)
from backend.applications.knowledge_base.schemas.knowledge_base_schema import (
    DocumentChunkUpdate,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
)
from backend.applications.user.models.user_model import User
from backend.configure import PROJECT_CONFIG
from backend.core.exceptions import (
    DataBaseStorageException,
    NoPermissionException,
    NotFoundException,
    ParameterException,
)


class _DocumentCreate(BaseModel):
    kb_id: str
    filename: str
    file_path: str
    file_size: int
    status: str = "processing"


class _DocumentUpdate(BaseModel):
    status: Optional[str] = None
    chunk_count: Optional[int] = None
    error_msg: Optional[str] = None


class _DocumentChunkCreate(BaseModel):
    doc_id: str
    content: str
    chunk_index: int


class DocumentCrud(ScaffoldCrud[Document, _DocumentCreate, _DocumentUpdate]):
    def __init__(self):
        super().__init__(model=Document)

    async def get_by_kb(self, kb_id: str, doc_id: str) -> Optional[Document]:
        """根据知识库 ID 和文档 ID 获取文档"""
        return await self.model.get_or_none(id=doc_id, kb_id=kb_id)

    async def list_by_kb(self, kb_id: str) -> List[Document]:
        """获取知识库下的文档列表"""
        return await self.model.filter(kb_id=kb_id).order_by("-created_time")

    async def count_by_kb(self, kb_id: str) -> int:
        """统计知识库下的文档数量"""
        return await self.model.filter(kb_id=kb_id).count()

    async def create_for_kb(self, kb_id: str, **kwargs) -> Document:
        """在指定知识库下创建文档"""
        return await self.model.create(kb_id=kb_id, **kwargs)


class DocumentChunkCrud(ScaffoldCrud[DocumentChunk, _DocumentChunkCreate, DocumentChunkUpdate]):
    def __init__(self):
        super().__init__(model=DocumentChunk)

    async def bulk_create_chunks(self, chunks: List[DocumentChunk]) -> None:
        """批量创建文档分块"""
        await self.model.bulk_create(chunks)

    async def list_by_kb(
        self,
        kb_id: str,
        doc_id: str = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[DocumentChunk]:
        """获取知识库下的文档分块列表"""
        qs = self.model.filter(doc__kb_id=kb_id)
        if doc_id:
            qs = qs.filter(doc_id=doc_id)
        offset = (page - 1) * page_size
        return await qs.order_by("chunk_index").offset(offset).limit(page_size)

    async def get_by_kb(self, kb_id: str, chunk_id: str) -> Optional[DocumentChunk]:
        """根据知识库 ID 和分块 ID 获取文档分块"""
        return (
            await self.model.filter(id=chunk_id, doc__kb_id=kb_id)
            .prefetch_related("doc")
            .first()
        )

    async def count_by_doc(self, doc_id: str) -> int:
        """统计文档下的分块数量"""
        return await self.model.filter(doc_id=doc_id).count()


class KnowledgeBaseCrud(ScaffoldCrud[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseCreate]):
    def __init__(self):
        super().__init__(model=KnowledgeBase)
        self.document = DocumentCrud()
        self.chunk = DocumentChunkCrud()

    async def get_by_id(self, kb_id: str) -> Optional[KnowledgeBase]:
        """根据 ID 获取知识库"""
        return await self.model.get_or_none(id=kb_id)

    async def list_for_user(
        self, user_id: int, search: str = None
    ) -> List[KnowledgeBase]:
        """获取用户可见的知识库列表"""
        qs = self.model.filter(Q(owner_id=user_id) | Q(is_public=True))
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        return await qs.order_by("-updated_time")

    def check_access(self, kb: KnowledgeBase, user: User) -> None:
        """校验知识库访问权限"""
        if not kb.is_public and kb.owner_id != user.id and not user.is_superuser:
            raise NoPermissionException(message="没有权限访问该知识库")

    def check_write(self, kb: KnowledgeBase, user: User) -> None:
        """校验知识库写权限"""
        if kb.owner_id != user.id and not user.is_superuser:
            raise NoPermissionException(message="没有权限操作该知识库")

    async def _to_out(self, kb: KnowledgeBase) -> KnowledgeBaseOut:
        doc_count = await self.document.count_by_kb(kb.id)
        return KnowledgeBaseOut(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            owner_id=kb.owner_id,
            is_public=kb.is_public,
            created_at=kb.created_time,
            updated_at=kb.updated_time,
            document_count=doc_count,
        )

    async def create_kb(self, user: User, data: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        """创建知识库"""
        kb = await self.model.create(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
        )
        return await self._to_out(kb)

    async def list_kbs(self, user: User, search: str = None) -> List[KnowledgeBaseOut]:
        """获取当前用户可见的知识库列表"""
        kbs = await self.list_for_user(user.id, search)
        return [await self._to_out(kb) for kb in kbs]

    async def get_kb(self, kb_id: str, user: User) -> KnowledgeBaseOut:
        """获取知识库详情"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        return await self._to_out(kb)

    async def update_kb(
        self, kb_id: str, user: User, data: KnowledgeBaseCreate
    ) -> KnowledgeBaseOut:
        """更新知识库"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        kb.name = data.name
        kb.description = data.description
        kb.is_public = data.is_public
        await kb.save()
        return await self._to_out(kb)

    async def delete_kb(self, kb_id: str, user: User) -> None:
        """删除知识库"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chroma_store.delete_by_kb(kb_id)
        kb_upload_dir = PROJECT_CONFIG.upload_path / kb_id
        if kb_upload_dir.exists():
            shutil.rmtree(kb_upload_dir)
        await kb.delete()

    async def upload_document(
        self, kb_id: str, user: User, file: UploadFile
    ) -> Document:
        """上传并处理文档"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)

        if not file.filename.endswith(".pdf"):
            raise ParameterException(message="仅支持PDF文件")

        kb_upload_dir = PROJECT_CONFIG.upload_path / kb_id
        kb_upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = kb_upload_dir / file.filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        doc = await self.document.create_for_kb(
            kb_id=kb_id,
            filename=file.filename,
            file_path=str(file_path),
            file_size=len(content),
            status="processing",
        )

        try:
            loader = PyMuPDFLoader(str(file_path))
            pages = loader.load()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=PROJECT_CONFIG.CHUNK_SIZE,
                chunk_overlap=PROJECT_CONFIG.CHUNK_OVERLAP,
                separators=["\n\n", "\n", "。", "；", "，", " ", ""],
            )

            chunk_models: List[DocumentChunk] = []
            chunk_index = 0
            for page in pages:
                for chunk_text in splitter.split_text(page.page_content):
                    chunk_models.append(
                        DocumentChunk(
                            id=str(uuid.uuid4()),
                            doc_id=doc.id,
                            content=chunk_text,
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

            await self.chunk.bulk_create_chunks(chunk_models)

            embeddings = get_embedding([c.content for c in chunk_models])
            chroma_chunks = [
                {
                    "doc_id": doc.id,
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "embedding": emb,
                }
                for chunk, emb in zip(chunk_models, embeddings)
            ]
            chroma_ids = chroma_store.upsert_chunks(kb_id, chroma_chunks)

            for chunk, chroma_id in zip(chunk_models, chroma_ids):
                chunk.chroma_id = chroma_id
                await chunk.save()

            doc.status = "completed"
            doc.chunk_count = len(chunk_models)
            await doc.save()
        except Exception as e:
            doc.status = "failed"
            doc.error_msg = str(e)
            await doc.save()
            raise DataBaseStorageException(message=f"文档处理失败: {str(e)}")

        return doc

    async def list_documents(self, kb_id: str, user: User) -> List[Document]:
        """获取知识库下的文档列表"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        return await self.document.list_by_kb(kb_id)

    async def delete_document(self, kb_id: str, doc_id: str, user: User) -> None:
        """删除文档"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        doc = await self.document.get_by_kb(kb_id, doc_id)
        if not doc:
            raise NotFoundException(message="文档不存在")
        chroma_store.delete_by_doc(doc_id)
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        await doc.delete()

    async def list_chunks(
        self,
        kb_id: str,
        user: User,
        doc_id: str = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[DocumentChunk]:
        """获取知识库下的文档分块列表"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        return await self.chunk.list_by_kb(kb_id, doc_id, page, page_size)

    async def get_chunk(self, kb_id: str, chunk_id: str, user: User) -> DocumentChunk:
        """获取文档分块详情"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_access(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")
        return chunk

    async def update_chunk(
        self, kb_id: str, chunk_id: str, user: User, data: DocumentChunkUpdate
    ) -> DocumentChunk:
        """更新文档分块"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")

        chunk.content = data.content
        embedding = get_embedding([data.content])[0]
        if chunk.chroma_id:
            chroma_store.delete_by_vector_id(chunk.chroma_id)
        chroma_ids = chroma_store.upsert_chunks(
            kb_id,
            [
                {
                    "doc_id": chunk.doc_id,
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "embedding": embedding,
                }
            ],
        )
        chunk.chroma_id = chroma_ids[0]
        await chunk.save()
        return chunk

    async def delete_chunk(self, kb_id: str, chunk_id: str, user: User) -> None:
        """删除文档分块"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise NotFoundException(message="知识库不存在")
        self.check_write(kb, user)
        chunk = await self.chunk.get_by_kb(kb_id, chunk_id)
        if not chunk:
            raise NotFoundException(message="知识块不存在")
        if chunk.chroma_id:
            chroma_store.delete_by_vector_id(chunk.chroma_id)
        doc_id = chunk.doc_id
        await chunk.delete()
        doc = await self.document.get_by_kb(kb_id, doc_id)
        if doc:
            doc.chunk_count = await self.chunk.count_by_doc(doc_id)
            await doc.save()
