import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION
from vector_store import VectorStore
from embedding_service import EmbeddingService
from chunking_service import ChunkingService
from tenant_manager import TenantManager
from metadata_store import MetadataStore
from file_parser import extract_text
from api_models import (
    CreateTenantRequest, TenantResponse,
    AddTextRequest, SearchRequest, DocumentResponse,
)
from models import SearchResult

DB_PATH = str(Path(__file__).parent / "data" / "metadata.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore(QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION)
    app.state.store = store
    app.state.embedder = EmbeddingService()
    app.state.chunker = ChunkingService()
    app.state.manager = TenantManager(store, app.state.embedder, app.state.chunker)
    app.state.metadata = MetadataStore(DB_PATH)
    yield
    store.close()
    app.state.metadata.close()


app = FastAPI(title="Embedding Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 租户管理 ──

@app.post("/api/tenants", response_model=TenantResponse)
def create_tenant(req: CreateTenantRequest):
    meta: MetadataStore = app.state.metadata
    if meta.get_tenant(req.tenant_id):
        raise HTTPException(409, f"租户 {req.tenant_id} 已存在")
    return meta.create_tenant(req.tenant_id, req.name)


@app.get("/api/tenants", response_model=list[TenantResponse])
def list_tenants():
    return app.state.metadata.list_tenants()


@app.delete("/api/tenants/{tenant_id}")
def delete_tenant(tenant_id: str):
    meta: MetadataStore = app.state.metadata
    manager: TenantManager = app.state.manager
    if not meta.get_tenant(tenant_id):
        raise HTTPException(404, f"租户 {tenant_id} 不存在")
    manager.delete_tenant(tenant_id)
    meta.delete_tenant(tenant_id)
    return {"ok": True}


# ── 文档管理 ──

def _check_tenant(tenant_id: str):
    if not app.state.metadata.get_tenant(tenant_id):
        raise HTTPException(404, f"租户 {tenant_id} 不存在")


@app.get("/api/tenants/{tenant_id}/documents", response_model=list[DocumentResponse])
def list_documents(tenant_id: str):
    _check_tenant(tenant_id)
    return app.state.metadata.list_documents(tenant_id)


@app.post("/api/tenants/{tenant_id}/documents/upload", response_model=DocumentResponse)
def upload_document(tenant_id: str, file: UploadFile = File(...)):
    _check_tenant(tenant_id)
    content = file.file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "文件大小不能超过 50MB")
    try:
        text = extract_text(file.filename, content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not text.strip():
        raise HTTPException(400, "文件内容为空")

    doc_id = str(uuid.uuid4())[:8]
    suffix = Path(file.filename).suffix.lower()
    manager: TenantManager = app.state.manager
    chunk_count = manager.add_document(
        tenant_id, doc_id, text, source=file.filename,
    )
    return app.state.metadata.add_document(
        tenant_id, doc_id, file.filename, suffix, len(content), file.filename, chunk_count,
    )


@app.post("/api/tenants/{tenant_id}/documents/text", response_model=DocumentResponse)
def add_text_document(tenant_id: str, req: AddTextRequest):
    _check_tenant(tenant_id)
    if not req.text.strip():
        raise HTTPException(400, "文本内容不能为空")

    doc_id = str(uuid.uuid4())[:8]
    manager: TenantManager = app.state.manager
    chunk_count = manager.add_document(
        tenant_id, doc_id, req.text, source=req.source,
    )
    return app.state.metadata.add_document(
        tenant_id, doc_id, None, "text", len(req.text.encode()), req.source, chunk_count,
    )


@app.delete("/api/tenants/{tenant_id}/documents/{doc_id}")
def delete_document(tenant_id: str, doc_id: str):
    _check_tenant(tenant_id)
    manager: TenantManager = app.state.manager
    manager.delete_document(tenant_id, doc_id)
    app.state.metadata.delete_document(tenant_id, doc_id)
    return {"ok": True}


# ── 搜索 ──

@app.post("/api/tenants/{tenant_id}/search", response_model=list[SearchResult])
def search(tenant_id: str, req: SearchRequest):
    _check_tenant(tenant_id)
    manager: TenantManager = app.state.manager
    return manager.search(tenant_id, req.query, req.top_k)


# ── 静态文件（生产模式） ──

dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True))
