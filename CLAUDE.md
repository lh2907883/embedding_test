# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Read Before Development

开始开发前必须先读 `narrative/DESIGN.md`，该文档包含完整的系统设计决策、数据模型、API 设计和已验证的测试场景，是恢复开发上下文的核心文档。

## Project Structure

Three independent modules sharing a monorepo:

- **backend/** — Multi-tenant vector embedding service (document upload, chunking, semantic search). Port 8000.
- **frontend/** — Vue 3 + Element Plus UI for backend. Port 5173 (dev).
- **narrative/** — AI game NPC agent: memory system, goal system, scene-driven LLM decision engine. Port 8001. Subdirectories: shared/, npc_agent/, event/, tests/.

backend and narrative are separate FastAPI services with independent Qdrant and SQLite databases. They do not share data or code at runtime.

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8000 --reload
```

### NPC Agent
```bash
cd narrative
pip install -r requirements.txt
uvicorn app:app --port 8001 --reload
# Test scenarios:
python tests/test_fight.py      # pure scene mode
python tests/test_fight.py 2    # preset event mode
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
Modular structure: `shared/` (infra), `npc_agent/` (NPC logic), `event/` (scene/decision logic). Main entry: `narrative/app.py`.

Two storage layers: **Qdrant** stores memories (each memory = one vector point, no chunking), **SQLite** stores NPC personality/traits and goals.

Key design decisions:
- **NPC = tenant** — each NPC's memories are isolated by npc_id payload filter
- **Memories are structured JSON entries**, not documents. No chunking needed.
- **Memory types**: background, action (I did X), affected (X happened to me), witnessed (I saw X), heard, thought
- **Emotions not stored** — LLM infers emotional state from personality + recent memories at decision time
- **Goals stored in SQLite** — only long-term life goals, not immediate reactions

**Scene-driven simulation** (`decision_engine.py`):
- Entry: `POST /api/scenes/simulate` (supports pure scene or preset event)
- Each round = one LLM call with ALL in-scene NPCs → unified coherent round_event (no contradictions)
- One round = one **situation change** (not a single action) — merges actions + process + result
- After all rounds: per-NPC LLM call generates first-person perspective memories
- Scene descriptions must be objective facts only (no hints, predictions, NPC intentions)
- Only existing NPCs allowed — LLM cannot invent new characters

### Embedding Model
Both services use `intfloat/multilingual-e5-large` (1024 dim) via fastembed (ONNX, no PyTorch). Uses `passage_embed` for documents/memories and `query_embed` for search queries — this distinction is required for cross-lingual retrieval.

### LLM Integration
NPC Agent uses DeepSeek V3 via OpenAI SDK (`api.deepseek.com`). API key in `narrative/.env`. Config loaded via python-dotenv (with `override=True`) in `config.py`.

## Conventions

- Game time is integer seconds starting from 0, elapsed_seconds per round decided by LLM
- All API responses use Chinese for user-facing messages
- Qdrant runs in local embedded mode (no server needed), with `force_disable_check_same_thread=True` for FastAPI thread pool compatibility
- SQLite uses WAL mode for concurrent access
- Payload indexes declared but only effective in Qdrant server mode (local mode ignores them, filtering still works)
