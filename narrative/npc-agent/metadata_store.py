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
            CREATE TABLE IF NOT EXISTS npc_goals (
                goal_id             TEXT PRIMARY KEY,
                npc_id              TEXT NOT NULL REFERENCES npcs(npc_id) ON DELETE CASCADE,
                goal_type           TEXT NOT NULL DEFAULT 'short_term',
                description         TEXT NOT NULL,
                priority            INTEGER NOT NULL DEFAULT 5,
                status              TEXT NOT NULL DEFAULT 'active',
                created_game_time   TEXT,
                deadline_game_time  TEXT,
                created_at          TEXT NOT NULL
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

    # ── 目标管理 ──

    def create_goal(self, goal_id: str, npc_id: str, goal_type: str, description: str,
                    priority: int, created_game_time: str | None, deadline_game_time: str | None) -> dict:
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO npc_goals
               (goal_id, npc_id, goal_type, description, priority, status, created_game_time, deadline_game_time, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (goal_id, npc_id, goal_type, description, priority, "active", created_game_time, deadline_game_time, now),
        )
        self.conn.commit()
        return {"goal_id": goal_id, "npc_id": npc_id, "goal_type": goal_type,
                "description": description, "priority": priority, "status": "active",
                "created_game_time": created_game_time, "deadline_game_time": deadline_game_time, "created_at": now}

    def list_goals(self, npc_id: str, status: str | None = "active") -> list[dict]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM npc_goals WHERE npc_id = ? AND status = ? ORDER BY priority DESC",
                (npc_id, status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM npc_goals WHERE npc_id = ? ORDER BY priority DESC",
                (npc_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_goal(self, goal_id: str, **kwargs) -> dict | None:
        row = self.conn.execute("SELECT * FROM npc_goals WHERE goal_id = ?", (goal_id,)).fetchone()
        if not row:
            return None
        updates = []
        values = []
        for key in ("status", "priority", "description", "deadline_game_time"):
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = ?")
                values.append(kwargs[key])
        if updates:
            values.append(goal_id)
            self.conn.execute(f"UPDATE npc_goals SET {', '.join(updates)} WHERE goal_id = ?", values)
            self.conn.commit()
        row = self.conn.execute("SELECT * FROM npc_goals WHERE goal_id = ?", (goal_id,)).fetchone()
        return dict(row) if row else None

    def delete_goal(self, goal_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM npc_goals WHERE goal_id = ?", (goal_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def close(self):
        self.conn.close()
