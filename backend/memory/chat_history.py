import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chat_history.db"

def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _migrate_sessions_mode(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "mode" not in cols:
        conn.execute(
            "ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'pirandello'"
        )


async def init_db():
    from backend.memory.user_memory import init_user_memory_table
    init_user_memory_table()
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'pirandello'
            )
        """)
        _migrate_sessions_mode(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_timestamp
            ON conversations (session_id, timestamp)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                last_msg_id INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        conn.close()

async def save_message(
    session_id: str, role: str, content: str, mode: str = "pirandello"
):
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        _migrate_sessions_mode(conn)

        # Ensure session exists
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            from backend.memory.session_titles import provisional_title

            title = provisional_title(content)
            session_mode = mode if mode in ("pirandello", "wiki") else "pirandello"
            cursor.execute(
                "INSERT INTO sessions (id, title, created_at, mode) VALUES (?, ?, ?, ?)",
                (session_id, title, datetime.now().isoformat(), session_mode),
            )
            
        cursor.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

async def get_history(session_id: str, limit: int = 6) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT role, content FROM conversations
               WHERE session_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (session_id, limit)
        ).fetchall()
        messages = []
        for row in reversed(rows):
            messages.append({"role": row["role"], "content": row["content"]})
        return messages
    finally:
        conn.close()

async def get_sessions(mode: str | None = None, query: str | None = None) -> list[dict]:
    conn = _get_conn()
    try:
        _migrate_sessions_mode(conn)
        q = (query or "").strip()
        like = f"%{q}%" if q else None

        if mode and mode in ("pirandello", "wiki"):
            if like:
                rows = conn.execute(
                    """SELECT DISTINCT s.id, s.title, s.created_at, s.mode
                       FROM sessions s
                       LEFT JOIN conversations c ON c.session_id = s.id
                       WHERE s.mode = ?
                         AND (s.title LIKE ? OR c.content LIKE ?)
                       ORDER BY s.created_at DESC""",
                    (mode, like, like),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, title, created_at, mode FROM sessions
                       WHERE mode = ? ORDER BY created_at DESC""",
                    (mode,),
                ).fetchall()
        elif like:
            rows = conn.execute(
                """SELECT DISTINCT s.id, s.title, s.created_at, s.mode
                   FROM sessions s
                   LEFT JOIN conversations c ON c.session_id = s.id
                   WHERE s.title LIKE ? OR c.content LIKE ?
                   ORDER BY s.created_at DESC""",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, created_at, mode FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "mode": row["mode"] if "mode" in row.keys() else "pirandello",
            }
            for row in rows
        ]
    finally:
        conn.close()


async def get_session_title(session_id: str) -> str | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT title FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row["title"] if row else None
    finally:
        conn.close()


async def update_session_title(session_id: str, title: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title.strip() or "Nuova conversazione", session_id),
        )
        conn.commit()
    finally:
        conn.close()


async def get_title_context_messages(session_id: str, limit: int = 4) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT role, content FROM conversations
               WHERE session_id = ?
               ORDER BY id ASC
               LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    finally:
        conn.close()


async def count_session_messages(session_id: str) -> int:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM conversations WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


async def get_session_mode(session_id: str) -> str | None:
    conn = _get_conn()
    try:
        _migrate_sessions_mode(conn)
        row = conn.execute(
            "SELECT mode FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return row["mode"] if "mode" in row.keys() else "pirandello"
    finally:
        conn.close()


async def create_session(session_id: str, title: str, mode: str = "pirandello"):
    conn = _get_conn()
    try:
        _migrate_sessions_mode(conn)
        session_mode = mode if mode in ("pirandello", "wiki") else "pirandello"
        conn.execute(
            """INSERT INTO sessions (id, title, created_at, mode) VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET mode = excluded.mode""",
            (session_id, title, datetime.now().isoformat(), session_mode),
        )
        conn.commit()
    finally:
        conn.close()

async def delete_session(session_id: str):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_summaries WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


async def clear_all_sessions(mode: str | None = None) -> int:
    """Elimina sessioni (tutte o solo per modalità). Restituisce quante sessioni sono state rimosse."""
    conn = _get_conn()
    try:
        _migrate_sessions_mode(conn)
        if mode and mode in ("pirandello", "wiki"):
            ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM sessions WHERE mode = ?", (mode,)
                ).fetchall()
            ]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM conversations WHERE session_id IN ({placeholders})", ids
            )
            conn.execute(
                f"DELETE FROM session_summaries WHERE session_id IN ({placeholders})",
                ids,
            )
            conn.execute("DELETE FROM sessions WHERE mode = ?", (mode,))
            conn.commit()
            return len(ids)
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM session_summaries")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        return count
    finally:
        conn.close()

async def clear_history(session_id: str):
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,)
        )
        conn.execute(
            "DELETE FROM session_summaries WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()
    finally:
        conn.close()

async def get_summary(session_id: str) -> tuple[str, int] | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT summary, last_msg_id FROM session_summaries WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        if row:
            return row["summary"], row["last_msg_id"]
        return None
    finally:
        conn.close()

async def save_summary(session_id: str, summary: str, last_msg_id: int):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO session_summaries (session_id, summary, last_msg_id) VALUES (?, ?, ?)",
            (session_id, summary, last_msg_id)
        )
        conn.commit()
    finally:
        conn.close()
