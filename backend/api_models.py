import uuid
from pydantic import BaseModel, Field
from typing import Optional


class CreateTenantRequest(BaseModel):
    tenant_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    created_at: str


class AddTextRequest(BaseModel):
    text: str
    source: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class DocumentResponse(BaseModel):
    doc_id: str
    tenant_id: str
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    source: Optional[str] = None
    chunk_count: int
    created_at: str
    updated_at: str
