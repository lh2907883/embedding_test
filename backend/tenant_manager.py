from typing import Optional
from models import ChunkMetadata, DocumentChunk, SearchResult
from vector_store import VectorStore
from embedding_service import EmbeddingService
from chunking_service import ChunkingService


class TenantManager:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        chunking_service: ChunkingService,
    ):
        self._store = vector_store
        self._embedder = embedding_service
        self._chunker = chunking_service

    def _build_chunks(
        self,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> list[DocumentChunk]:
        chunk_texts = self._chunker.chunk_text(text)
        embeddings = self._embedder.embed_documents(chunk_texts)
        chunks = []
        for i, (chunk_text, emb) in enumerate(zip(chunk_texts, embeddings)):
            chunks.append(
                DocumentChunk(
                    id=f"{tenant_id}:{doc_id}:{i}",
                    text=chunk_text,
                    embedding=emb,
                    metadata=ChunkMetadata(
                        tenant_id=tenant_id,
                        doc_id=doc_id,
                        chunk_id=f"{doc_id}_chunk_{i}",
                        chunk_index=i,
                        source=source,
                        extra=extra_metadata,
                    ),
                )
            )
        return chunks

    def add_document(
        self,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> int:
        chunks = self._build_chunks(tenant_id, doc_id, text, source, extra_metadata)
        self._store.upsert_chunks(chunks)
        return len(chunks)

    def update_document(
        self,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> int:
        chunks = self._build_chunks(tenant_id, doc_id, text, source, extra_metadata)
        self._store.upsert_chunks(chunks)
        self._store.delete_orphan_chunks(tenant_id, doc_id, max_valid_index=len(chunks) - 1)
        return len(chunks)

    def delete_document(self, tenant_id: str, doc_id: str) -> None:
        self._store.delete_document(tenant_id, doc_id)

    def delete_tenant(self, tenant_id: str) -> None:
        self._store.delete_tenant(tenant_id)

    def search(
        self, tenant_id: str, query: str, top_k: int = 5,
    ) -> list[SearchResult]:
        query_vector = self._embedder.embed_query(query)
        results = self._store.search(tenant_id, query_vector, top_k)
        return [
            SearchResult(
                chunk_id=r.payload["chunk_id"],
                doc_id=r.payload["doc_id"],
                text=r.payload["text"],
                score=r.score,
                metadata=r.payload,
            )
            for r in results
        ]
