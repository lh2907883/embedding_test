import uuid
from qdrant_client import QdrantClient, models
from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION
from models import DocumentChunk


class VectorStore:
    def __init__(
        self,
        storage_path: str = QDRANT_STORAGE_PATH,
        collection_name: str = COLLECTION_NAME,
        dimension: int = EMBEDDING_DIMENSION,
    ):
        self.client = QdrantClient(path=storage_path, force_disable_check_same_thread=True)
        self.collection_name = collection_name
        self._ensure_collection(dimension)

    def _ensure_collection(self, dimension: int):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            # payload index 仅在 Qdrant server 模式下生效
            # 本地嵌入式模式过滤仍然可用，只是没有索引加速
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="doc_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass

    @staticmethod
    def _make_point_id(tenant_id: str, doc_id: str, chunk_index: int) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}:{doc_id}:{chunk_index}"))

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        points = [
            models.PointStruct(
                id=self._make_point_id(
                    c.metadata.tenant_id, c.metadata.doc_id, c.metadata.chunk_index
                ),
                vector=c.embedding,
                payload={
                    "tenant_id": c.metadata.tenant_id,
                    "doc_id": c.metadata.doc_id,
                    "chunk_id": c.metadata.chunk_id,
                    "chunk_index": c.metadata.chunk_index,
                    "text": c.text,
                    "source": c.metadata.source,
                    **(c.metadata.extra or {}),
                },
            )
            for c in chunks
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self, tenant_id: str, query_vector: list[float], top_k: int = 5,
    ) -> list:
        return self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=tenant_id),
                    )
                ]
            ),
            limit=top_k,
            with_payload=True,
        ).points

    def delete_document(self, tenant_id: str, doc_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        ),
                    ]
                )
            ),
        )

    def delete_tenant(self, tenant_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        )
                    ]
                )
            ),
        )

    def delete_orphan_chunks(
        self, tenant_id: str, doc_id: str, max_valid_index: int
    ) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        ),
                        models.FieldCondition(
                            key="chunk_index",
                            range=models.Range(gt=max_valid_index),
                        ),
                    ]
                )
            ),
        )

    def close(self):
        self.client.close()
