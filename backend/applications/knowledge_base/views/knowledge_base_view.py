from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from backend.services.rag_auth import get_current_user
from backend.applications.user.models.user_model import User
from backend.applications.knowledge_base.schemas.knowledge_base_schema import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    DocumentOut,
    DocumentChunkOut,
    DocumentChunkUpdate,
)
from backend.applications.knowledge_base.services.knowledge_base_crud import KnowledgeBaseCrud
from backend.applications.knowledge_base.dependencies import get_knowledge_base_crud

knowledge_base = APIRouter(tags=["knowledge_base"])


# ---------- 知识库 ----------

@knowledge_base.post("/", response_model=KnowledgeBaseOut)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    return await kb_crud.create_kb(current_user, kb_data)


@knowledge_base.get("/", response_model=List[KnowledgeBaseOut])
async def list_knowledge_bases(
    search: str = None,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    return await kb_crud.list_kbs(current_user, search)


@knowledge_base.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    return await kb_crud.get_kb(kb_id, current_user)


@knowledge_base.put("/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: str,
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    return await kb_crud.update_kb(kb_id, current_user, kb_data)


@knowledge_base.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    await kb_crud.delete_kb(kb_id, current_user)
    return {"detail": "知识库已删除"}


@knowledge_base.post("/{kb_id}/documents", response_model=DocumentOut)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    doc = await kb_crud.upload_document(kb_id, current_user, file)
    return DocumentOut(
        id=doc.id,
        kb_id=doc.kb_id,
        filename=doc.filename,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        created_at=doc.created_time,
    )


@knowledge_base.get("/{kb_id}/documents", response_model=List[DocumentOut])
async def list_documents(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    docs = await kb_crud.list_documents(kb_id, current_user)
    return [
        DocumentOut(
            id=d.id,
            kb_id=d.kb_id,
            filename=d.filename,
            file_size=d.file_size,
            chunk_count=d.chunk_count,
            status=d.status,
            created_at=d.created_time,
        )
        for d in docs
    ]


@knowledge_base.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    await kb_crud.delete_document(kb_id, doc_id, current_user)
    return {"detail": "文档已删除"}


@knowledge_base.get("/{kb_id}/chunks", response_model=List[DocumentChunkOut])
async def list_chunks(
    kb_id: str,
    doc_id: str = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    chunks = await kb_crud.list_chunks(
        kb_id, current_user, doc_id, page, page_size
    )
    return [
        DocumentChunkOut(
            id=c.id,
            doc_id=c.doc_id,
            content=c.content,
            chunk_index=c.chunk_index,
            created_at=c.created_time,
        )
        for c in chunks
    ]


@knowledge_base.get("/{kb_id}/chunks/{chunk_id}", response_model=DocumentChunkOut)
async def get_chunk(
    kb_id: str,
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    chunk = await kb_crud.get_chunk(kb_id, chunk_id, current_user)
    return DocumentChunkOut(
        id=chunk.id,
        doc_id=chunk.doc_id,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
        created_at=chunk.created_time,
    )


@knowledge_base.put("/{kb_id}/chunks/{chunk_id}", response_model=DocumentChunkOut)
async def update_chunk(
    kb_id: str,
    chunk_id: str,
    chunk_data: DocumentChunkUpdate,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    chunk = await kb_crud.update_chunk(
        kb_id, chunk_id, current_user, chunk_data
    )
    return DocumentChunkOut(
        id=chunk.id,
        doc_id=chunk.doc_id,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
        created_at=chunk.created_time,
    )


@knowledge_base.delete("/{kb_id}/chunks/{chunk_id}")
async def delete_chunk(
    kb_id: str,
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    kb_crud: KnowledgeBaseCrud = Depends(get_knowledge_base_crud),
):
    await kb_crud.delete_chunk(kb_id, chunk_id, current_user)
    return {"detail": "知识块已删除"}
