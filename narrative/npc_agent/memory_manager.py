import uuid
from shared.models import MemoryEntry, MemorySearchResult, MemoryType
from npc_agent.api_models import AddMemoryRequest
from shared.vector_store import VectorStore
from shared.embedding_service import EmbeddingService


class NpcMemoryManager:
    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        self._store = vector_store
        self._embedder = embedding_service

    def add_memory(self, npc_id: str, req: AddMemoryRequest) -> MemoryEntry:
        memory_id = str(uuid.uuid4())
        embedding = self._embedder.embed_documents([req.content])[0]
        entry = MemoryEntry(
            memory_id=memory_id,
            npc_id=npc_id,
            memory_type=req.memory_type,
            game_time=req.game_time,
            content=req.content,
            source_npc_id=req.source_npc_id,
            related_npc_ids=req.related_npc_ids,
            location=req.location,
        )
        self._store.upsert_memories([entry], [embedding])
        return entry

    def add_memories_batch(self, npc_id: str, memories: list[AddMemoryRequest]) -> list[MemoryEntry]:
        contents = [m.content for m in memories]
        embeddings = self._embedder.embed_documents(contents)
        entries = []
        for m, emb in zip(memories, embeddings):
            entry = MemoryEntry(
                memory_id=str(uuid.uuid4()),
                npc_id=npc_id,
                memory_type=m.memory_type,
                game_time=m.game_time,
                content=m.content,
                source_npc_id=m.source_npc_id,
                related_npc_ids=m.related_npc_ids,
                location=m.location,
            )
            entries.append(entry)
        self._store.upsert_memories(entries, embeddings)
        return entries

    def search_memories(
        self, npc_id: str, query: str, top_k: int = 10,
        memory_type: str | None = None,
        related_npc_id: str | None = None,
    ) -> list[MemorySearchResult]:
        query_vector = self._embedder.embed_query(query)
        results = self._store.search_memories(
            npc_id, query_vector, top_k,
            memory_type=memory_type,
            related_npc_id=related_npc_id,
        )
        return [
            MemorySearchResult(
                memory_id=r.id,
                npc_id=r.payload["npc_id"],
                content=r.payload["content"],
                score=r.score,
                memory_type=r.payload["memory_type"],
                game_time=r.payload["game_time"],
                source_npc_id=r.payload.get("source_npc_id"),
                related_npc_ids=r.payload.get("related_npc_ids", []),
                location=r.payload.get("location"),
            )
            for r in results
        ]

    def list_memories(self, npc_id: str, limit: int = 50) -> list[dict]:
        points, _ = self._store.list_memories(npc_id, limit=limit)
        memories = [
            {
                "memory_id": p.id,
                "npc_id": p.payload["npc_id"],
                "memory_type": p.payload["memory_type"],
                "game_time": p.payload["game_time"],
                "content": p.payload["content"],
                "source_npc_id": p.payload.get("source_npc_id"),
                "related_npc_ids": p.payload.get("related_npc_ids", []),
                "location": p.payload.get("location"),
            }
            for p in points
        ]
        memories.sort(key=lambda m: int(m["game_time"]) if m["game_time"].lstrip("-").isdigit() else 0)
        return memories

    def delete_memory(self, memory_id: str) -> None:
        self._store.delete_memory(memory_id)

    def delete_npc_memories(self, npc_id: str) -> None:
        self._store.delete_npc_memories(npc_id)

    def count_memories(self, npc_id: str) -> int:
        return self._store.count_memories(npc_id)
