from qdrant_client import QdrantClient, models
from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION
from shared.models import MemoryEntry


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
            for field in ("npc_id", "memory_type", "source_npc_id", "related_npc_ids", "location"):
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

    def upsert_memories(self, memories: list[MemoryEntry], embeddings: list[list[float]]) -> None:
        points = [
            models.PointStruct(
                id=m.memory_id,
                vector=emb,
                payload={
                    "npc_id": m.npc_id,
                    "memory_type": m.memory_type.value,
                    "game_time": m.game_time,
                    "content": m.content,
                    "source_npc_id": m.source_npc_id,
                    "related_npc_ids": m.related_npc_ids,
                    "location": m.location,
                },
            )
            for m, emb in zip(memories, embeddings)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search_memories(
        self,
        npc_id: str,
        query_vector: list[float],
        top_k: int = 10,
        memory_type: str | None = None,
        related_npc_id: str | None = None,
    ) -> list:
        conditions = [
            models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))
        ]
        if memory_type:
            conditions.append(
                models.FieldCondition(key="memory_type", match=models.MatchValue(value=memory_type))
            )
        if related_npc_id:
            conditions.append(
                models.FieldCondition(key="related_npc_ids", match=models.MatchAny(any=[related_npc_id]))
            )
        return self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=models.Filter(must=conditions),
            limit=top_k,
            with_payload=True,
        ).points

    def list_memories(self, npc_id: str, limit: int = 50, offset: str | None = None):
        return self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))]
            ),
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

    def delete_memory(self, memory_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=[memory_id]),
        )

    def delete_npc_memories(self, npc_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))]
                )
            ),
        )

    def count_memories(self, npc_id: str) -> int:
        return self.client.count(
            collection_name=self.collection_name,
            count_filter=models.Filter(
                must=[models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))]
            ),
        ).count

    def close(self):
        self.client.close()
