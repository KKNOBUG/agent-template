import os
import shutil
import uuid
from typing import List

from fastapi import HTTPException, UploadFile, status
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.configure import PROJECT_CONFIG
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.knowledge_base.models.knowledge_base_model import KnowledgeBase, Document, DocumentChunk
from backend.applications.knowledge_base.services.knowledge_base_repo import KnowledgeBaseRepository
from backend.applications.knowledge_base.schemas.knowledge_base_schema import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    DocumentChunkUpdate,
)
from backend.applications.base.rag.embeddings import get_embedding
from backend.applications.base.rag.chroma_store import chroma_store


class KnowledgeBaseService:
    @staticmethod
    def check_access(kb: KnowledgeBase, user: User) -> None:
        if not kb.is_public and kb.owner_id != user.id and not user.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="没有权限访问该知识库")

    @staticmethod
    def check_write(kb: KnowledgeBase, user: User) -> None:
        if kb.owner_id != user.id and not user.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="没有权限操作该知识库")

    @staticmethod
    async def _to_out(kb: KnowledgeBase) -> KnowledgeBaseOut:
        doc_count = await KnowledgeBaseRepository.count_documents(kb.id)
        return KnowledgeBaseOut(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            owner_id=kb.owner_id,
            is_public=kb.is_public,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count,
        )

    @classmethod
    async def create(cls, user: User, data: KnowledgeBaseCreate) -> KnowledgeBaseOut:
        kb = await KnowledgeBaseRepository.create(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
        )
        return await cls._to_out(kb)

    @classmethod
    async def list_kbs(cls, user: User, search: str = None) -> List[KnowledgeBaseOut]:
        kbs = await KnowledgeBaseRepository.list_for_user(user.id, search)
        return [await cls._to_out(kb) for kb in kbs]

    @classmethod
    async def get_kb(cls, kb_id: str, user: User) -> KnowledgeBaseOut:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_access(kb, user)
        return await cls._to_out(kb)

    @classmethod
    async def update_kb(
        cls, kb_id: str, user: User, data: KnowledgeBaseCreate
    ) -> KnowledgeBaseOut:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)
        kb.name = data.name
        kb.description = data.description
        kb.is_public = data.is_public
        await kb.save()
        return await cls._to_out(kb)

    @classmethod
    async def delete_kb(cls, kb_id: str, user: User) -> None:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)
        chroma_store.delete_by_kb(kb_id)
        kb_upload_dir = PROJECT_CONFIG.upload_path / kb_id
        if kb_upload_dir.exists():
            shutil.rmtree(kb_upload_dir)
        await KnowledgeBaseRepository.delete(kb)

    @classmethod
    async def upload_document(
        cls, kb_id: str, user: User, file: UploadFile
    ) -> Document:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)

        if not file.filename.endswith(".pdf"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="仅支持PDF文件")

        kb_upload_dir = PROJECT_CONFIG.upload_path / kb_id
        kb_upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = kb_upload_dir / file.filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        doc = await KnowledgeBaseRepository.create_document(
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

            await KnowledgeBaseRepository.bulk_create_chunks(chunk_models)

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
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文档处理失败: {str(e)}",
            )

        return doc

    @classmethod
    async def list_documents(cls, kb_id: str, user: User) -> List[Document]:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_access(kb, user)
        return await KnowledgeBaseRepository.list_documents(kb_id)

    @classmethod
    async def delete_document(cls, kb_id: str, doc_id: str, user: User) -> None:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)
        doc = await KnowledgeBaseRepository.get_document(kb_id, doc_id)
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
        chroma_store.delete_by_doc(doc_id)
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        await KnowledgeBaseRepository.delete_document(doc)

    @classmethod
    async def list_chunks(
        cls, kb_id: str, user: User, doc_id: str = None, page: int = 1, page_size: int = 50
    ) -> List[DocumentChunk]:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_access(kb, user)
        return await KnowledgeBaseRepository.list_chunks(kb_id, doc_id, page, page_size)

    @classmethod
    async def get_chunk(cls, kb_id: str, chunk_id: str, user: User) -> DocumentChunk:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_access(kb, user)
        chunk = await KnowledgeBaseRepository.get_chunk(kb_id, chunk_id)
        if not chunk:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识块不存在")
        return chunk

    @classmethod
    async def update_chunk(
        cls, kb_id: str, chunk_id: str, user: User, data: DocumentChunkUpdate
    ) -> DocumentChunk:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)
        chunk = await KnowledgeBaseRepository.get_chunk(kb_id, chunk_id)
        if not chunk:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识块不存在")

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

    @classmethod
    async def delete_chunk(cls, kb_id: str, chunk_id: str, user: User) -> None:
        kb = await KnowledgeBaseRepository.get_by_id(kb_id)
        if not kb:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识库不存在")
        cls.check_write(kb, user)
        chunk = await KnowledgeBaseRepository.get_chunk(kb_id, chunk_id)
        if not chunk:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="知识块不存在")
        if chunk.chroma_id:
            chroma_store.delete_by_vector_id(chunk.chroma_id)
        doc_id = chunk.doc_id
        await KnowledgeBaseRepository.delete_chunk(chunk)
        doc = await KnowledgeBaseRepository.get_document(kb_id, doc_id)
        if doc:
            doc.chunk_count = await KnowledgeBaseRepository.count_chunks_by_doc(doc_id)
            await doc.save()
