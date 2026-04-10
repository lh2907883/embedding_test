from pydantic import BaseModel, Field
from typing import Optional


class ChunkMetadata(BaseModel):
    tenant_id: str
    doc_id: str
    chunk_id: str
    chunk_index: int
    source: Optional[str] = None
    extra: Optional[dict] = None


class DocumentChunk(BaseModel):
    id: str
    text: str
    embedding: Optional[list[float]] = None
    metadata: ChunkMetadata


class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict
