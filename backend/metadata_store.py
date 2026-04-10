import sqlite3
from datetime import datetime
from pathlib import Path


class MetadataStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id   TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                doc_id      TEXT NOT NULL,
                tenant_id   TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                filename    TEXT,
                file_type   TEXT,
                file_size   INTEGER,
                source      TEXT,
                chunk_count INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (tenant_id, doc_id)
            );
        """)
        self.conn.commit()

    def create_tenant(self, tenant_id: str, name: str) -> dict:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO tenants (tenant_id, name, created_at) VALUES (?, ?, ?)",
            (tenant_id, name, now),
        )
        self.conn.commit()
        return {"tenant_id": tenant_id, "name": name, "created_at": now}

    def list_tenants(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT tenant_id, name, created_at FROM tenants ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tenant(self, tenant_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT tenant_id, name, created_at FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        return dict(row) if row else None

    def delete_tenant(self, tenant_id: str) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def add_document(
        self,
        tenant_id: str,
        doc_id: str,
        filename: str | None,
        file_type: str | None,
        file_size: int | None,
        source: str | None,
        chunk_count: int,
    ) -> dict:
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO documents
               (doc_id, tenant_id, filename, file_type, file_size, source, chunk_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, tenant_id, filename, file_type, file_size, source, chunk_count, now, now),
        )
        self.conn.commit()
        return {
            "doc_id": doc_id, "tenant_id": tenant_id, "filename": filename,
            "file_type": file_type, "file_size": file_size, "source": source,
            "chunk_count": chunk_count, "created_at": now, "updated_at": now,
        }

    def list_documents(self, tenant_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM documents WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, tenant_id: str, doc_id: str) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM documents WHERE tenant_id = ? AND doc_id = ?",
            (tenant_id, doc_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def close(self):
        self.conn.close()
