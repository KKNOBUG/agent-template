from typing import Optional, List

from tortoise.expressions import Q

from backend.applications.knowledge_base.models.knowledge_base_model import KnowledgeBase, Document, DocumentChunk


class KnowledgeBaseRepository:
    @staticmethod
    async def create(owner_id: str, **kwargs) -> KnowledgeBase:
        return await KnowledgeBase.create(owner_id=owner_id, **kwargs)

    @staticmethod
    async def get_by_id(kb_id: str) -> Optional[KnowledgeBase]:
        return await KnowledgeBase.get_or_none(id=kb_id)

    @staticmethod
    async def list_for_user(user_id: str, search: str = None) -> List[KnowledgeBase]:
        qs = KnowledgeBase.filter(Q(owner_id=user_id) | Q(is_public=True))
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        return await qs.order_by("-updated_at")

    @staticmethod
    async def count_documents(kb_id: str) -> int:
        return await Document.filter(kb_id=kb_id).count()

    @staticmethod
    async def delete(kb: KnowledgeBase) -> None:
        await kb.delete()

    @staticmethod
    async def create_document(kb_id: str, **kwargs) -> Document:
        return await Document.create(kb_id=kb_id, **kwargs)

    @staticmethod
    async def get_document(kb_id: str, doc_id: str) -> Optional[Document]:
        return await Document.get_or_none(id=doc_id, kb_id=kb_id)

    @staticmethod
    async def list_documents(kb_id: str) -> List[Document]:
        return await Document.filter(kb_id=kb_id).order_by("-created_at")

    @staticmethod
    async def delete_document(doc: Document) -> None:
        await doc.delete()

    @staticmethod
    async def bulk_create_chunks(chunks: List[DocumentChunk]) -> None:
        await DocumentChunk.bulk_create(chunks)

    @staticmethod
    async def list_chunks(
        kb_id: str, doc_id: str = None, page: int = 1, page_size: int = 50
    ) -> List[DocumentChunk]:
        qs = DocumentChunk.filter(doc__kb_id=kb_id)
        if doc_id:
            qs = qs.filter(doc_id=doc_id)
        offset = (page - 1) * page_size
        return await qs.order_by("chunk_index").offset(offset).limit(page_size)

    @staticmethod
    async def get_chunk(kb_id: str, chunk_id: str) -> Optional[DocumentChunk]:
        return (
            await DocumentChunk.filter(id=chunk_id, doc__kb_id=kb_id)
            .prefetch_related("doc")
            .first()
        )

    @staticmethod
    async def delete_chunk(chunk: DocumentChunk) -> None:
        await chunk.delete()

    @staticmethod
    async def count_chunks_by_doc(doc_id: str) -> int:
        return await DocumentChunk.filter(doc_id=doc_id).count()
