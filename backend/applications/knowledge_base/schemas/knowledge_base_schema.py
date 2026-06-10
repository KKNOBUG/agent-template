from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = False


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: int
    is_public: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_size: int
    chunk_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkOut(BaseModel):
    id: str
    doc_id: str
    content: str
    chunk_index: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkUpdate(BaseModel):
    content: str = Field(..., min_length=1)
