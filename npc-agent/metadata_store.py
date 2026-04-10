import json
import sqlite3
from datetime import datetime
from pathlib import Path


class MetadataStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS npcs (
                npc_id      TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                personality TEXT NOT NULL DEFAULT '',
                traits      TEXT NOT NULL DEFAULT '{}',
                faction     TEXT,
                location    TEXT,
                created_at  TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def create_npc(self, npc_id: str, name: str, personality: str, traits: dict,
                   faction: str | None, location: str | None) -> dict:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO npcs (npc_id, name, personality, traits, faction, location, created_at) VALUES (?,?,?,?,?,?,?)",
            (npc_id, name, personality, json.dumps(traits, ensure_ascii=False), faction, location, now),
        )
        self.conn.commit()
        return {"npc_id": npc_id, "name": name, "personality": personality,
                "traits": traits, "faction": faction, "location": location, "created_at": now}

    def list_npcs(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM npcs ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["traits"] = json.loads(d["traits"])
            result.append(d)
        return result

    def get_npc(self, npc_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM npcs WHERE npc_id = ?", (npc_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["traits"] = json.loads(d["traits"])
        return d

    def update_npc(self, npc_id: str, **kwargs) -> dict | None:
        npc = self.get_npc(npc_id)
        if not npc:
            return None
        updates = []
        values = []
        for key in ("name", "personality", "traits", "faction", "location"):
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = ?")
                val = kwargs[key]
                if key == "traits":
                    val = json.dumps(val, ensure_ascii=False)
                values.append(val)
        if updates:
            values.append(npc_id)
            self.conn.execute(f"UPDATE npcs SET {', '.join(updates)} WHERE npc_id = ?", values)
            self.conn.commit()
        return self.get_npc(npc_id)

    def delete_npc(self, npc_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM npcs WHERE npc_id = ?", (npc_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def close(self):
        self.conn.close()
