"""
Eigene, kleine SQLite-Datenbank für Session-/Anfragen-Metadaten und den
Rationale-Spiegel - getrennt von checkpoints.sqlite (siehe config.py).

WAL + busy_timeout: SqliteSaver (LangGraph) schützt seine EIGENE Connection
bereits über einen internen threading.Lock (siehe
langgraph/checkpoint/sqlite/__init__.py: `self.lock = threading.Lock()`,
jede cursor()-Nutzung geht dadurch) und setzt beim ersten setup()-Aufruf
selbst `PRAGMA journal_mode=WAL`. Für UNSERE eigene, separate Connection
hier gilt das nicht automatisch - wir spiegeln das Muster bewusst nach:
ein globaler Lock um jede Connection-Nutzung UND WAL/busy_timeout explizit
gesetzt. Damit sollte "database is locked" innerhalb dieses einen Prozesses
nicht auftreten (siehe Bericht an die Nutzerin für die ausführlichere
Begründung, warum kein zusätzliches Retry nötig ist).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA busy_timeout=5000;

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS anfragen (
                    thread_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_anfragen_session
                    ON anfragen(session_id);

                CREATE TABLE IF NOT EXISTS message_rationale (
                    thread_id TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    rationale_json TEXT NOT NULL,
                    PRIMARY KEY (thread_id, message_index)
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- Sessions -----------------------------------------------------

    def create_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
                (session_id, now_iso()),
            )
            self._conn.commit()

    def session_exists(self, session_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
            )
            return cur.fetchone() is not None

    # --- Anfragen -------------------------------------------------------

    def create_anfrage(
        self, thread_id: str, session_id: str, title: Optional[str] = None
    ) -> dict:
        ts = now_iso()
        with self._lock:
            self._conn.execute(
                """INSERT INTO anfragen
                   (thread_id, session_id, title, created_at, last_active_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (thread_id, session_id, title, ts, ts),
            )
            self._conn.commit()
        return {
            "thread_id": thread_id,
            "title": title,
            "created_at": ts,
            "last_active_at": ts,
        }

    def get_anfrage(self, thread_id: str) -> Optional[dict]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT thread_id, session_id, title, created_at, last_active_at
                   FROM anfragen WHERE thread_id = ?""",
                (thread_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "thread_id": row[0],
            "session_id": row[1],
            "title": row[2],
            "created_at": row[3],
            "last_active_at": row[4],
        }

    def list_anfragen(self, session_id: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT thread_id, title, created_at, last_active_at
                   FROM anfragen WHERE session_id = ?
                   ORDER BY created_at ASC""",
                (session_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "thread_id": r[0],
                "title": r[1],
                "created_at": r[2],
                "last_active_at": r[3],
            }
            for r in rows
        ]

    def active_thread_id(self, session_id: str) -> Optional[str]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT thread_id FROM anfragen WHERE session_id = ?
                   ORDER BY last_active_at DESC LIMIT 1""",
                (session_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def touch_anfrage(self, thread_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE anfragen SET last_active_at = ? WHERE thread_id = ?",
                (now_iso(), thread_id),
            )
            self._conn.commit()

    def set_title_if_empty(self, thread_id: str, title: str) -> bool:
        """Setzt den Titel nur, wenn noch keiner gesetzt ist (siehe Auftrag
        Punkt 4: "danach nicht mehr geändert"). Gibt True zurück, wenn der
        Titel durch diesen Aufruf tatsächlich gesetzt wurde (für
        anfrage_titled-Event)."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE anfragen SET title = ? WHERE thread_id = ? AND title IS NULL",
                (title, thread_id),
            )
            self._conn.commit()
            return cur.rowcount == 1

    # --- Rationale-Spiegel ------------------------------------------------
    # Siehe rationale.py/graph_runner.py: der Graph-State selbst persistiert
    # keine Rationale pro Nachricht (state["messages"] sind reine
    # {role, content}-Dicts). Wir spiegeln rationale hier zusätzlich,
    # indiziert über die (stabile, weil append-only) Position der Nachricht
    # in state["messages"], damit GET /thread/{id} sie nach einem Reload
    # wiederfindet - siehe Bericht an die Nutzerin für die Grenzen davon
    # (vorbelegte Anfragen haben keinen Spiegel-Eintrag, zeigen also
    # rationale: null).

    def save_message_rationale(
        self, thread_id: str, message_index: int, rationale: dict
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO message_rationale
                   (thread_id, message_index, rationale_json) VALUES (?, ?, ?)""",
                (thread_id, message_index, json.dumps(rationale, ensure_ascii=False)),
            )
            self._conn.commit()

    def get_all_rationales(self, thread_id: str) -> dict[int, dict]:
        with self._lock:
            cur = self._conn.execute(
                """SELECT message_index, rationale_json FROM message_rationale
                   WHERE thread_id = ?""",
                (thread_id,),
            )
            rows = cur.fetchall()
        return {int(idx): json.loads(raw) for idx, raw in rows}
