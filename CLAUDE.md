# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Read Before Development

开始开发前必须先读 `narrative/DESIGN.md`，该文档包含完整的系统设计决策、数据模型、API 设计和已验证的测试场景，是恢复开发上下文的核心文档。

## Project Structure

Three independent modules sharing a monorepo:

- **backend/** — Multi-tenant vector embedding service (document upload, chunking, semantic search). Port 8000.
- **frontend/** — Vue 3 + Element Plus UI for backend. Port 5173 (dev).
- **narrative/npc-agent/** — AI game NPC agent: memory system, goal system, LLM decision engine. Port 8001.

backend and narrative/npc-agent are separate FastAPI services with independent Qdrant and SQLite databases. They do not share data or code at runtime.

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8000 --reload
```

### NPC Agent
```bash
cd narrative/npc-agent
pip install -r requirements.txt
uvicorn app:app --port 8001 --reload
# Test scenario:
python test_fight.py  # requires service running on 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # dev server, proxies /api → localhost:8000
npm run build        # production build to dist/
```

## Architecture

### Backend (Document Embedding)
Layered: `app.py` (FastAPI endpoints) → `tenant_manager.py` (orchestration) → `vector_store.py` (Qdrant) + `metadata_store.py` (SQLite). Documents are chunked via `chunking_service.py`, embedded via `embedding_service.py` (fastembed), stored in Qdrant with tenant_id payload isolation. Tenant/document metadata in SQLite. File parsing (`file_parser.py`) handles PDF/Word/Excel/TXT.

### NPC Agent (Narrative System)
Two storage layers: **Qdrant** stores memories (each memory = one vector point, no chunking), **SQLite** stores NPC personality/traits and goals.

Key design decisions:
- **NPC = tenant** — each NPC's memories are isolated by npc_id payload filter
- **Memories are structured JSON entries**, not documents. No chunking needed.
- **Relationships stored as memories** (memory_type: "relationship") with related_npc_ids field, not in a separate table. Relationships change through events.
- **Emotions not stored** — LLM infers emotional state from personality + recent memories at decision time
- **Goals stored in SQLite** — they have lifecycle status (active/completed/failed/abandoned), need enumeration not semantic search

**Decision loop** (`decision_engine.py`): External injects event → find affected NPCs by location + intensity → write witness memories → each NPC calls LLM (personality + goals + relevant memories + event) → LLM outputs structured JSON (action, dialogue, memory_note, new_events, goal_changes) → process output → new_events trigger next round → loop until stable or max rounds.

Event propagation is NPC-driven: the system only handles "who is present", subsequent spreading (who tells who, with what distortion) emerges from NPC decisions.

### Embedding Model
Both services use `intfloat/multilingual-e5-large` (1024 dim) via fastembed (ONNX, no PyTorch). Uses `passage_embed` for documents/memories and `query_embed` for search queries — this distinction is required for cross-lingual retrieval.

### LLM Integration
NPC Agent uses Anthropic Claude (Sonnet) via `anthropic` SDK. API key in `narrative/.env`. Config loaded via python-dotenv in `config.py`.

## Conventions

- Game time is an arbitrary ordered string (T001, T002...), not real timestamps
- All API responses use Chinese for user-facing messages
- Qdrant runs in local embedded mode (no server needed), with `force_disable_check_same_thread=True` for FastAPI thread pool compatibility
- SQLite uses WAL mode for concurrent access
- Payload indexes declared but only effective in Qdrant server mode (local mode ignores them, filtering still works)
